"""Service layer shared by the CLI and the Streamlit UI.

Orchestrates the existing pieces (cases, note fetching/extraction, the jury,
persistence) behind a few UI-friendly functions, and supports building a case
from EITHER fetched note IDs OR pasted note text (the FHIR escape hatch).
"""

import os
import re
import glob
import json
import uuid

import cases
import persistence
from note_extractor import extract_note, make_manual_note
from jury import run_jury, default_panel

CASE_SOURCES = [cases.CASES_DIR, os.path.join("examples", "cases")]


def _slug(text, fallback="case"):
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40] or fallback


# ----------------------------------------------------------------- clients
def make_fetch_client():
    """Lazily build the live Epic client (only needed to fetch notes by ID)."""
    from epic_client import EpicFHIRClient

    return EpicFHIRClient()


def panel_info():
    """Current jury mode + panel, for the UI header."""
    mode = os.getenv("JURY_MODE", "stub").lower()
    members = [f"{m.provider}:{m.model}" for m in default_panel()]
    return {"mode": mode, "members": members}


# ------------------------------------------------------------------ cases
def list_cases():
    """All ingested summaries (cases) across data/ and examples/, with score."""
    out, seen = [], set()
    for directory in CASE_SOURCES:
        for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
            try:
                with open(path) as f:
                    case = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            cid = case.get("case_id") or os.path.splitext(os.path.basename(path))[0]
            if cid in seen:
                continue
            seen.add(cid)
            verdict = persistence.load_verdict(cid)
            summary = (case.get("summary", {}) or {}).get("text") or ""
            out.append(
                {
                    "case_id": cid,
                    "path": path,
                    "summary_preview": summary[:160],
                    "source": (case.get("summary", {}) or {}).get("source"),
                    "source_note_ids": case.get("source_note_ids", []),
                    "overall": verdict.get("overall_score") if verdict else None,
                    "judged": verdict is not None,
                }
            )
    return sorted(out, key=lambda c: c["case_id"])


def _resolve_case_path(ref):
    if ref.endswith(".json") and os.path.exists(ref):
        return ref
    for directory in CASE_SOURCES:
        path = os.path.join(directory, f"{cases._safe(ref)}.json")
        if os.path.exists(path):
            return path
    return None


def load_case(ref):
    path = _resolve_case_path(ref)
    if not path:
        raise FileNotFoundError(f"No case '{ref}' in {CASE_SOURCES}")
    return cases.load_case(path)


def create_case(summary_text, case_id=None, note_ids=None, pasted_notes=None, summary_source="manual"):
    """Create + persist a case from a summary plus any mix of fetched note IDs
    and pasted note bodies. Pasted notes are stored as manual notes so they are
    referenced by id exactly like fetched ones. Returns the case dict.
    """
    if not (summary_text or "").strip():
        raise ValueError("A summary is required.")
    note_ids = [n.strip() for n in (note_ids or []) if n and n.strip()]
    pasted_notes = [p for p in (pasted_notes or []) if (p.get("text") if isinstance(p, dict) else p)]
    if not note_ids and not pasted_notes:
        raise ValueError("Provide at least one reference note (an ID or pasted text).")

    case_id = (case_id or "").strip() or f"{_slug(summary_text)}-{uuid.uuid4().hex[:4]}"

    manual_ids = []
    for i, p in enumerate(pasted_notes):
        text = p.get("text") if isinstance(p, dict) else p
        note = make_manual_note(
            text,
            note_type=(p.get("type") if isinstance(p, dict) else None) or "Pasted note",
            date=(p.get("date") if isinstance(p, dict) else None),
            note_id=f"manual-{_slug(case_id)}-{i + 1}",
        )
        persistence.save_note(note)
        manual_ids.append(note["document_reference_id"])

    cases.create_case(
        case_id,
        note_ids + manual_ids,
        summary_text=summary_text,
        summary_source=summary_source,
    )
    return cases.load_case(case_id)


# ------------------------------------------------------------------ notes
def gather_notes(note_ids, client=None):
    """Resolve notes by id: cached first, then fetch via client. Manual (pasted)
    notes are always cached. Returns (notes, missing_ids)."""
    notes, missing = [], []
    for nid in note_ids:
        cached = persistence.load_note_by_id(nid)
        if cached:
            notes.append(cached)
            continue
        if client is None:
            missing.append(nid)
            continue
        try:
            resolved = client.resolve_document_reference(nid)
            note = extract_note(
                resolved["resource"], client,
                resolved_via=resolved["resolved_via"], original_id=nid,
            )
            persistence.save_note(note)
            notes.append(note)
        except Exception:
            missing.append(nid)
    return notes, missing


def case_notes(case):
    """Notes already available for a case (cached/manual), plus missing ids.
    Does not hit the network -- fetching happens at judge time."""
    return gather_notes(case.get("source_note_ids", []), client=None)


def load_verdict(case_id):
    return persistence.load_verdict(case_id)


def judge_case(case, fetch_missing=None):
    """Run the jury for a case against the totality of its notes. Cached and
    pasted notes are always used; uncached-by-id notes are fetched from Epic only
    when live (JURY_MODE=live), so stub mode stays fully offline. Persists and
    returns (verdict, missing)."""
    if fetch_missing is None:
        fetch_missing = os.getenv("JURY_MODE", "stub").lower() == "live"
    client = make_fetch_client() if fetch_missing else None
    notes, missing = gather_notes(case.get("source_note_ids", []), client=client)
    if not notes:
        raise RuntimeError(
            f"No notes available for case '{case.get('case_id')}'. Missing: {missing}. "
            "Stub mode uses only cached/pasted notes; set JURY_MODE=live (+ Epic creds) "
            "to fetch notes by ID."
        )
    verdict = run_jury(notes, cases.summary_text(case), case_id=case["case_id"])
    persistence.save_verdict(verdict)
    return verdict, missing
