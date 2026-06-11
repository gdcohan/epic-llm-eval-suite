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
import hashlib
from collections import defaultdict
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()  # so JURY_MODE / JURY_PANEL / API keys in .env reach the UI too

import cases
import persistence
import config
from note_extractor import extract_note, make_manual_note
from jury import run_jury

CASE_SOURCES = [cases.CASES_DIR, os.path.join("examples", "cases")]

HARM_CATEGORIES = ["medication/dosing", "allergy", "diagnosis", "test/result",
                   "follow-up/plan", "demographic/admin", "other"]
_SEV_ORDER = {"low": 1, "moderate": 2, "severe": 3}


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
    members = [f"{m.provider}:{m.model}" for m in config.active_panel()]
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


# ----------------------------------------------------------- adjudication
def get_adjudication(case_id):
    return persistence.load_adjudication(case_id)


def finding_key(dimension, member, summary_quote, note_quote):
    """Stable content-hash id for one juror's finding (label-per-juror, V1)."""
    raw = "|".join([dimension or "", member or "",
                    (summary_quote or "").strip(), (note_quote or "").strip()])
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def set_finding_label(case_id, key, label, meta):
    """Set/clear a human label on one jury finding. label: 'valid' | 'false_alarm'
    | None (clear). meta carries dimension/spans/member for later metrics."""
    adj = persistence.load_adjudication(case_id) or {"case_id": case_id, "dimensions": {}, "rationales": {}}
    adj.setdefault("finding_labels", {})
    if label is None:
        adj["finding_labels"].pop(key, None)
    else:
        adj["finding_labels"][key] = {"label": label, **meta}
    adj["adjudicated_at"] = datetime.now(timezone.utc).isoformat()
    persistence.save_adjudication(adj)
    return adj


def precision_stats():
    """Finding-level precision across all labeled cases: of the jury's flagged
    findings the human reviewed, how many were valid (vs false alarms)."""
    tp, fp = defaultdict(int), defaultdict(int)
    false_alarms = []
    labeled_cases = 0
    for c in list_cases():
        adj = persistence.load_adjudication(c["case_id"])
        labels = (adj or {}).get("finding_labels") or {}
        if not labels:
            continue
        labeled_cases += 1
        for lbl in labels.values():
            dim = lbl.get("dimension")
            if lbl.get("label") == "valid":
                tp[dim] += 1
            elif lbl.get("label") == "false_alarm":
                fp[dim] += 1
                false_alarms.append({"case": c["case_id"], **lbl})
    per_dim = {}
    for d in sorted(set(list(tp) + list(fp))):
        t, f = tp[d], fp[d]
        per_dim[d] = {"labeled": t + f, "validated": t, "false_alarms": f,
                      "precision": round(t / (t + f), 2) if (t + f) else None}
    total_t, total_f = sum(tp.values()), sum(fp.values())
    return {
        "per_dimension": per_dim,
        "labeled_cases": labeled_cases,
        "total_labeled": total_t + total_f,
        "overall_precision": round(total_t / (total_t + total_f), 2) if (total_t + total_f) else None,
        "false_alarms": false_alarms,
    }


def set_dimension_adjudication(case_id, dimension, score, rationale, adjudicator):
    """Set (or clear, when score is None) one dimension's human override, merging
    into any existing adjudication. Keeps a per-dimension rationale."""
    adj = persistence.load_adjudication(case_id) or {"case_id": case_id, "dimensions": {}, "rationales": {}}
    adj.setdefault("dimensions", {})
    adj.setdefault("rationales", {})
    if score is None:
        adj["dimensions"].pop(dimension, None)
        adj["rationales"].pop(dimension, None)
    else:
        adj["dimensions"][dimension] = int(score)
        if (rationale or "").strip():
            adj["rationales"][dimension] = rationale.strip()
        else:
            adj["rationales"].pop(dimension, None)
    adj["adjudicator"] = (adjudicator or "").strip()
    adj["adjudicated_at"] = datetime.now(timezone.utc).isoformat()
    persistence.save_adjudication(adj)
    return adj


def overview_stats():
    """Aggregate stats across all cases for the Overview dashboard."""
    cases = list_cases()
    rows, dims_order = [], []
    dim_scores, dim_issues = defaultdict(list), defaultdict(int)
    harm_matrix = defaultdict(lambda: defaultdict(int))  # category -> severity -> #cases
    harm_matrix_cases = defaultdict(lambda: defaultdict(list))  # category -> severity -> [case_id]
    severe_cases = 0
    n_judged = 0

    for c in cases:
        verdict = persistence.load_verdict(c["case_id"])
        if not verdict:
            rows.append({"case": c["case_id"], "overall": None, "issues": None,
                         "agreement": "pending", "judged": False})
            continue
        n_judged += 1
        splits = verdict.get("split_dimensions") or []
        adj_dims = (persistence.load_adjudication(c["case_id"]) or {}).get("dimensions", {})
        row = {"case": c["case_id"], "overall": verdict.get("overall_score"),
               "issues": 0, "agreement": "split" if splits else "agreed", "judged": True}
        case_cells, case_sevs = set(), set()  # case-level harm (robust to juror count)
        for d in verdict.get("dimensions", []):
            name = d["dimension"]
            if name not in dims_order:
                dims_order.append(name)
            # human-final score: adjudicated override if present, else jury mean
            final = adj_dims.get(name, d.get("mean_score"))
            row[name] = final
            if isinstance(final, (int, float)):
                dim_scores[name].append(final)
            for f in d.get("findings", []):
                if f.get("type") != "issue":
                    continue
                dim_issues[name] += 1
                row["issues"] += 1
                sev = (f.get("harm_severity") or "").strip().lower()
                if sev in _SEV_ORDER:
                    case_sevs.add(sev)
                    cat = (f.get("harm_category") or "other").strip() or "other"
                    case_cells.add((cat, sev))
        row["max_harm"] = max(case_sevs, key=lambda s: _SEV_ORDER[s]) if case_sevs else ""
        if "severe" in case_sevs:
            severe_cases += 1
        for cat, sev in case_cells:
            harm_matrix[cat][sev] += 1
            harm_matrix_cases[cat][sev].append(c["case_id"])
        row["adjudicated"] = ("✎ " + ", ".join(sorted(adj_dims))) if adj_dims else ""
        rows.append(row)

    overalls = [r["overall"] for r in rows if isinstance(r.get("overall"), (int, float))]
    kpis = {
        "cases": len(cases),
        "judged": n_judged,
        "avg_overall": round(sum(overalls) / len(overalls), 2) if overalls else None,
        "with_issues": sum(1 for r in rows if r.get("issues")),
        "severe_cases": severe_cases,
        "splits": sum(1 for r in rows if r.get("agreement") == "split"),
    }
    return {
        "rows": rows,
        "dims": dims_order,
        "kpis": kpis,
        "avg_by_dim": {d: round(sum(s) / len(s), 2) for d, s in dim_scores.items() if s},
        "issues_by_dim": dict(dim_issues),
        "harm_matrix": {cat: dict(sevs) for cat, sevs in harm_matrix.items()},
        "harm_matrix_cases": {cat: dict(sevs) for cat, sevs in harm_matrix_cases.items()},
    }


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
    verdict = run_jury(notes, cases.summary_text(case), case_id=case["case_id"],
                       dimensions=config.active_dimensions(), panel=config.active_panel(),
                       source_guidance=config.active_source_guidance(),
                       output_contract=config.active_output_contract())
    persistence.save_verdict(verdict)
    return verdict, missing


def judge_adhoc(summary_text, note_ids=None, pasted_notes=None):
    """Ephemeral judge for the Live Judge scratchpad: build notes from pasted text
    (in-memory, not persisted) and/or fetched IDs, then run the jury. Returns
    (verdict, notes, missing) without persisting anything."""
    if not (summary_text or "").strip():
        raise ValueError("A summary is required.")
    notes = []
    for i, p in enumerate(pasted_notes or []):
        text = p.get("text") if isinstance(p, dict) else p
        if text and str(text).strip():
            notes.append(make_manual_note(str(text), note_id=f"adhoc-{i + 1}"))
    missing = []
    ids = [n.strip() for n in (note_ids or []) if n and n.strip()]
    if ids:
        client = make_fetch_client() if os.getenv("JURY_MODE", "stub").lower() == "live" else None
        fetched, missing = gather_notes(ids, client=client)
        notes += fetched
    if not notes:
        raise RuntimeError("Provide at least one reference note (paste text, or a fetchable ID in live mode).")
    verdict = run_jury(notes, summary_text,
                       dimensions=config.active_dimensions(), panel=config.active_panel(),
                       source_guidance=config.active_source_guidance(),
                       output_contract=config.active_output_contract())
    return verdict, notes, missing
