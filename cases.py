"""Evaluation cases: a candidate summary + the set of source note IDs it was
drawn from. This manifest is the join between a summary and its notes -- the
unit the jury actually evaluates (one summary vs. the totality of its notes).

A case lives at data/cases/<case_id>.json and references notes by their
DocumentReference ID (the same ID you fetch by), so notes are never duplicated.
The summary is stored inline by default, with an optional file path for long ones.
"""

import os
import re
import json
from datetime import datetime, timezone

CASES_DIR = os.path.join("data", "cases")


def _safe(name):
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(name))[:120] or "case"


def case_path(case_id, base_dir=CASES_DIR):
    return os.path.join(base_dir, f"{_safe(case_id)}.json")


def create_case(case_id, source_note_ids, summary_text=None, summary_path=None,
                summary_source="manual", generated_at=None, base_dir=CASES_DIR):
    """Build and persist a case manifest."""
    if not source_note_ids:
        raise ValueError("A case needs at least one source note ID.")
    if not (summary_text or summary_path):
        raise ValueError("A case needs a summary (inline text or a file path).")
    case = {
        "case_id": case_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "text": summary_text,
            "path": summary_path,
            "source": summary_source,        # e.g. "epic-genai" | "manual"
            "generated_at": generated_at,     # when the summary itself was produced
        },
        "source_note_ids": list(source_note_ids),
    }
    return save_case(case, base_dir)


def save_case(case, base_dir=CASES_DIR):
    path = case_path(case["case_id"], base_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(case, f, indent=2)
    return path


def load_case(ref, base_dir=CASES_DIR):
    """Load a case by ID, or by direct path (e.g. an example under examples/)."""
    path = ref if (ref.endswith(".json") and os.path.exists(ref)) else case_path(ref, base_dir)
    with open(path) as f:
        return json.load(f)


def summary_text(case):
    """Return the candidate summary text, reading the file if stored by path."""
    summary = case.get("summary", {}) or {}
    if summary.get("text"):
        return summary["text"]
    if summary.get("path"):
        with open(summary["path"]) as f:
            return f.read()
    raise ValueError(f"Case '{case.get('case_id')}' has no summary text or path.")
