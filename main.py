"""CLI for the Epic note-fetch + LLM-as-jury POC.

Commands:
  demo                          End-to-end on mock data, offline (no creds/keys).
  fetch    --ids ... | --ids-file f.txt
                                Resolve note IDs -> normalized notes -> data/notes/.
  judge    --note-file n.json --summary s.txt [--summary-text "..."]
                                Run the jury on a persisted note vs. a candidate summary.
  run      --ids ... --summary s.txt
                                Fetch + persist + judge in one shot.
  discover [--patient ID]       List DocumentReference IDs for sandbox test patients.

The jury REQUIRES a candidate summary (the Epic GenAI summary you're evaluating).
Jury mode is controlled by env: JURY_MODE=stub (default, offline) or live.
"""

import os
import sys
import json
import argparse

from epic_client import EpicFHIRClient
from note_extractor import extract_note
from jury import run_jury, print_verdict
import persistence

# Epic sandbox test patients (salvaged from the original SDOH scaffolding) --
# useful for `discover` when you don't have note IDs yet.
SANDBOX_PATIENTS = {
    "erXuFYUfucBZaryVksYEcMg3": "Jason Argonaut",
    "eNR.A-e9uE.T6p8X06p7A.A3": "James Bond",
    "e63Sjt-79659E8nMeTr9uWw3": "Camila Lopez",
}


def _collect_ids(args):
    ids = list(args.ids or [])
    if args.ids_file:
        with open(args.ids_file) as f:
            ids += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    if not ids:
        sys.exit("No note IDs provided (use --ids or --ids-file).")
    return ids


def _read_summary(args):
    if getattr(args, "summary_text", None):
        return args.summary_text
    if getattr(args, "summary", None):
        with open(args.summary) as f:
            return f.read()
    sys.exit("A candidate summary is required (use --summary or --summary-text).")


def fetch_notes(ids, client):
    notes = []
    for nid in ids:
        print(f"👉 Resolving note ID: {nid}")
        try:
            resolved = client.resolve_document_reference(nid)
            note = extract_note(
                resolved["resource"],
                client,
                resolved_via=resolved["resolved_via"],
                original_id=nid,
            )
            path = persistence.save_note(note)
            print(f"   ✅ {note['metadata']['type']} via {note['resolved_via']} "
                  f"({len(note['combined_text'])} chars) -> {path}")
            notes.append(note)
        except Exception as exc:
            print(f"   ❌ {nid}: {exc}")
    return notes


def cmd_fetch(args):
    fetch_notes(_collect_ids(args), EpicFHIRClient())


def cmd_judge(args):
    note = persistence.load_note(args.note_file)
    verdict = run_jury(note, _read_summary(args))
    print_verdict(verdict)
    print(f"\nSaved verdict -> {persistence.save_verdict(verdict)}")


def cmd_run(args):
    summary = _read_summary(args)
    for note in fetch_notes(_collect_ids(args), EpicFHIRClient()):
        verdict = run_jury(note, summary)
        print_verdict(verdict)
        persistence.save_verdict(verdict)


def cmd_discover(args):
    client = EpicFHIRClient()
    patients = {args.patient: "(provided)"} if args.patient else SANDBOX_PATIENTS
    for pid, name in patients.items():
        print(f"\n🔎 {name} ({pid})")
        try:
            for d in client.discover_document_references(pid):
                print(f"   {d['id']}  [{d['type']}]  {d['date']}")
        except Exception as exc:
            print(f"   ❌ {exc}")


def cmd_demo(args):
    from mock_client import MockFHIRClient

    print("=== DEMO (offline mock data) ===")
    client = MockFHIRClient()
    note = fetch_notes(["mock-note-progress-001"], client)[0]
    print(f"\n--- Combined note text ({len(note['combined_text'])} chars) ---")
    print(note["combined_text"])
    print(f"\nLinked/embedded docs resolved: "
          f"{[r['relationship'] + ':' + str(r['target_id']) for r in note['related']]}")

    summary_path = os.path.join("mock_data", "candidate_summary.txt")
    with open(summary_path) as f:
        summary = f.read()
    verdict = run_jury(note, summary)
    print_verdict(verdict)
    persistence.save_verdict(verdict)
    print("\n(JURY_MODE=stub by default; set JURY_MODE=live + API keys for real judgments.)")


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    def add_ids(sp):
        sp.add_argument("--ids", nargs="*", help="Note IDs (any supported shape).")
        sp.add_argument("--ids-file", help="File with one note ID per line.")

    def add_summary(sp):
        sp.add_argument("--summary", help="Path to candidate summary text file.")
        sp.add_argument("--summary-text", help="Candidate summary as an inline string.")

    sp = sub.add_parser("demo", help="Offline end-to-end on mock data.")
    sp.set_defaults(func=cmd_demo)

    sp = sub.add_parser("fetch", help="Fetch + persist notes by ID.")
    add_ids(sp)
    sp.set_defaults(func=cmd_fetch)

    sp = sub.add_parser("judge", help="Run the jury on a persisted note.")
    sp.add_argument("--note-file", required=True, help="Path to a persisted note JSON.")
    add_summary(sp)
    sp.set_defaults(func=cmd_judge)

    sp = sub.add_parser("run", help="Fetch + persist + judge in one shot.")
    add_ids(sp)
    add_summary(sp)
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("discover", help="List DocumentReference IDs for sandbox patients.")
    sp.add_argument("--patient", help="Patient FHIR ID (defaults to sandbox test patients).")
    sp.set_defaults(func=cmd_discover)

    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
