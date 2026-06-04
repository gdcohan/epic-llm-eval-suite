"""CLI for the Epic note-fetch + LLM-as-jury POC.

Commands:
  demo                          End-to-end on mock data, offline (no creds/keys).
  fetch     --ids ... | --ids-file f.txt
                                Resolve note IDs -> normalized notes -> data/notes/.
  case      --id ID --notes ... --summary(-text) ...
                                Create an eval-case manifest (summary + its note IDs).
  judge-case --case ID [--mock] Judge a case: summary vs. the TOTALITY of its notes.
  judge     --note-file n.json --summary s.txt
                                Quick single-note judge (legacy convenience).
  run       --ids ... --summary s.txt
                                Fetch notes and judge the summary against all of them.
  discover  [--patient ID]      List DocumentReference IDs for sandbox test patients.

The jury REQUIRES a candidate summary (the Epic GenAI summary you're evaluating)
and judges it against the totality of its source notes. Jury mode is controlled
by env: JURY_MODE=stub (default, offline) or live.
"""

import os
import sys
import argparse

import requests

from epic_client import EpicFHIRClient
from note_extractor import extract_note
from jury import run_jury, print_verdict
import persistence
import cases
import config

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


def _gather_notes(ids, client):
    """Return notes for the given IDs, reusing the local cache before fetching."""
    notes = []
    for nid in ids:
        cached = persistence.load_note_by_id(nid)
        if cached:
            print(f"   • cached: {nid}")
            notes.append(cached)
            continue
        print(f"   • fetching: {nid}")
        resolved = client.resolve_document_reference(nid)
        note = extract_note(
            resolved["resource"], client,
            resolved_via=resolved["resolved_via"], original_id=nid,
        )
        persistence.save_note(note)
        notes.append(note)
    return notes


def _make_client(args):
    if getattr(args, "mock", False):
        from mock_client import MockFHIRClient
        return MockFHIRClient()
    return EpicFHIRClient()


def cmd_fetch(args):
    fetch_notes(_collect_ids(args), EpicFHIRClient())


def cmd_case(args):
    path = cases.create_case(
        args.id,
        _collect_ids(args),
        summary_text=getattr(args, "summary_text", None),
        summary_path=getattr(args, "summary", None),
        summary_source=args.summary_source,
    )
    print(f"✅ Created case '{args.id}' -> {path}")


def cmd_judge_case(args):
    case = cases.load_case(args.case)
    print(f"⚖️  Judging case '{case['case_id']}' against "
          f"{len(case['source_note_ids'])} source note(s)")
    notes = _gather_notes(case["source_note_ids"], _make_client(args))
    verdict = run_jury(notes, cases.summary_text(case), case_id=case["case_id"],
                       dimensions=config.active_dimensions(), panel=config.active_panel(),
                       source_guidance=config.active_source_guidance(),
                       output_contract=config.active_output_contract())
    print_verdict(verdict)
    print(f"\nSaved verdict -> {persistence.save_verdict(verdict)}")


def cmd_judge(args):
    note = persistence.load_note(args.note_file)
    verdict = run_jury(note, _read_summary(args))
    print_verdict(verdict)
    print(f"\nSaved verdict -> {persistence.save_verdict(verdict)}")


def cmd_run(args):
    summary = _read_summary(args)
    notes = fetch_notes(_collect_ids(args), EpicFHIRClient())
    verdict = run_jury(notes, summary, dimensions=config.active_dimensions(), panel=config.active_panel(),
                       source_guidance=config.active_source_guidance(),
                       output_contract=config.active_output_contract())
    print_verdict(verdict)
    persistence.save_verdict(verdict)


def cmd_discover(args):
    client = EpicFHIRClient()
    patients = {args.patient: "(provided)"} if args.patient else SANDBOX_PATIENTS
    for pid, name in patients.items():
        print(f"\n🔎 {name} ({pid})")
        try:
            results = client.discover_document_references(pid)
            if not results:
                print("   (no DocumentReferences for this patient)")
            for d in results:
                print(f"   {d['id']}  [{d['type']}]  {d['date']}")
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "?"
            print(f"   ⚠️  unavailable (HTTP {code}) — this test-patient ID may be "
                  f"stale for the current sandbox; try another.")
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

    sp = sub.add_parser("case", help="Create an eval-case manifest (summary + note IDs).")
    sp.add_argument("--id", required=True, help="Case ID.")
    add_ids(sp)
    add_summary(sp)
    sp.add_argument("--summary-source", default="manual",
                    help="Provenance of the summary, e.g. 'epic-genai' or 'manual'.")
    sp.set_defaults(func=cmd_case)

    sp = sub.add_parser("judge-case", help="Judge a case vs. the totality of its notes.")
    sp.add_argument("--case", required=True, help="Case ID or path to a case JSON.")
    sp.add_argument("--mock", action="store_true", help="Use offline mock FHIR client.")
    sp.set_defaults(func=cmd_judge_case)

    sp = sub.add_parser("judge", help="Quick single-note judge (legacy).")
    sp.add_argument("--note-file", required=True, help="Path to a persisted note JSON.")
    add_summary(sp)
    sp.set_defaults(func=cmd_judge)

    sp = sub.add_parser("run", help="Fetch notes and judge the summary against all of them.")
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
