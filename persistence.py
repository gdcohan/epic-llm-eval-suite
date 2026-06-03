"""Local JSON persistence for fetched notes and jury verdicts."""

import os
import re
import json

NOTES_DIR = os.path.join("data", "notes")
VERDICTS_DIR = os.path.join("data", "verdicts")


def _safe(name):
    return re.sub(r"[^A-Za-z0-9._-]", "_", str(name))[:120] or "unknown"


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)
    return path


def save_note(note, base_dir=NOTES_DIR):
    """Persist one normalized note as JSON; returns the file path."""
    name = note.get("document_reference_id") or note.get("input_id") or "note"
    return _write_json(os.path.join(base_dir, f"{_safe(name)}.json"), note)


def load_note(path):
    with open(path) as f:
        return json.load(f)


def save_verdict(verdict, base_dir=VERDICTS_DIR):
    """Persist a jury verdict as JSON; returns the file path."""
    name = verdict.get("document_reference_id") or verdict.get("note_id") or "verdict"
    return _write_json(os.path.join(base_dir, f"{_safe(name)}.json"), verdict)
