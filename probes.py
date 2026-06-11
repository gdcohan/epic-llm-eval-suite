"""Omission-probe harness: does the comprehensiveness judge catch planted
omissions?

Each probe file (see probes/) holds one shared note set, a faithful base
summary, and variants that each delete exactly ONE clinically significant
fact. The harness runs the target dimension's jury on every variant and
reports, per planted omission, which jurors caught it (matched by terms
against each finding's quotes/explanation) — plus false omissions on the
control variant. This is the regression suite for judge-prompt tuning.

Run (live mode for real results; stub emits no findings):
    JURY_MODE=live python probes.py
    python probes.py --file probes/omission_probes.json
"""

import os
import sys
import json
import argparse

from dotenv import load_dotenv

load_dotenv()

import config  # noqa: E402
from jury import run_jury  # noqa: E402
from note_extractor import make_manual_note  # noqa: E402

DEFAULT_FILE = os.path.join("probes", "omission_probes.json")


def _finding_text(f):
    return " ".join(
        str(f.get(k) or "") for k in ("note_quote", "summary_quote", "explanation")
    ).lower()


def _matching_members(issues, match_terms):
    terms = [t.lower() for t in match_terms]
    return sorted({
        f.get("member") or "?"
        for f in issues
        if any(t in _finding_text(f) for t in terms)
    })


def run_probe_file(path):
    with open(path) as fh:
        spec = json.load(fh)

    dim_name = spec.get("dimension", "comprehensiveness")
    dims = [d for d in config.active_dimensions() if d.name == dim_name]
    if not dims:
        sys.exit(f"No active dimension named '{dim_name}' — check Jury Config.")
    panel = config.active_panel()

    notes = [
        make_manual_note(n["text"], note_type=n.get("type"), date=n.get("date"),
                         note_id=f"probe-note-{i + 1}")
        for i, n in enumerate(spec["notes"])
    ]

    if os.getenv("JURY_MODE", "stub").lower() != "live":
        print("⚠ JURY_MODE is not 'live' — the stub jury emits no findings, so every "
              "probe will read as missed. Set JURY_MODE=live (+ API keys) for real results.\n")

    print(f"Probing '{dim_name}' with {len(panel)} juror(s): {', '.join(m.name for m in panel)}")
    print(f"{len(spec['probes'])} probe(s) from {path}\n")

    caught_total = planted_total = 0
    per_member_hits = {m.name: 0 for m in panel}

    for probe in spec["probes"]:
        verdict = run_jury(
            notes, probe["summary"],
            dimensions=dims, panel=panel,
            source_guidance=config.active_source_guidance(),
            output_contract=config.active_output_contract(),
        )
        d = verdict["dimensions"][0]
        issues = [f for f in d.get("findings", []) if f.get("type") == "issue"]
        errors = [v for v in d.get("verdicts", []) if v.get("error")]

        print(f"── {probe['probe_id']}   score {d.get('mean_score')} / {d.get('scale')} "
              f"[{d.get('agreement')}] · {len(issues)} issue finding(s)")
        for e in errors:
            print(f"   ⚠ juror error · {e.get('member')}: {e['error']}")

        if not probe["planted"]:
            # control: any omission finding here is a false alarm
            if issues:
                print(f"   ✗ control flagged {len(issues)} issue(s) — false omissions:")
                for f in issues:
                    print(f"     - [{f.get('member')}] {f.get('explanation')}")
            else:
                print("   ✓ control clean (no false omissions)")
            print()
            continue

        for planted in probe["planted"]:
            planted_total += 1
            hits = _matching_members(issues, planted.get("match_terms", []))
            for m in hits:
                if m in per_member_hits:
                    per_member_hits[m] += 1
            if hits:
                caught_total += 1
                print(f"   ✓ CAUGHT  ({planted.get('harm_severity')}) {planted['description']}"
                      f"  — by {', '.join(hits)}")
            else:
                print(f"   ✗ MISSED  ({planted.get('harm_severity')}) {planted['description']}")
        print()

    print("=" * 60)
    if planted_total:
        print(f"Panel probe recall: {caught_total}/{planted_total} planted omissions caught "
              f"({caught_total / planted_total:.0%})")
        for member, hits in per_member_hits.items():
            print(f"  - {member}: {hits}/{planted_total} ({hits / planted_total:.0%})")
    else:
        print("No planted omissions in this probe file.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file", default=DEFAULT_FILE, help=f"probe file (default {DEFAULT_FILE})")
    run_probe_file(ap.parse_args().file)
