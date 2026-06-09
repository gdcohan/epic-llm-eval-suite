# Handoff

Transition notes only — what a new session needs to pick up *right now*. Anything
durable lives in `README.md` (how it works + module map + concepts) and
`ROADMAP.md` (plan + design notes + key decisions).

**Working branch:** `claude/brave-meitner-2Tqc2` (develop + push here; no PRs unless asked).

## Current state / in-flight

**Live flows are validated** (ROADMAP §1 done): the demo cases run through the real
panel, planted errors get caught, verbatim highlights land, harm/severity is sane.
The old "BIG gap" (no live run) is closed — real findings, harm badges, and the
Calibrate precision numbers are now meaningful. The app is also validated in stub
mode (offline) and via Streamlit `AppTest`.

- **Demo-ready.** Recent demo polish: harm-matrix cell drill-down, click-to-focus
  summary highlighting, scorecard autoscroll on filter.
- **Next up:** complete calibration (ROADMAP §4) now that there are real findings to
  label — **de novo probe authoring**, then **recall (finding-level)**. Also queued:
  Live-Judge pin/compare, few-shot anchoring V1.
- **Reminder:** stub emits no findings, so harm/precision/findings are still empty
  in stub mode — exercise these against a live run.

## Gotchas that bite a new session

- **`data/` is gitignored** and local to the container — cases, notes, verdicts,
  adjudications, `jury_config.json`. Nothing transfers across sessions; re-run
  `python examples/generate_demo_cases.py` to reseed the 5 demo cases. (Two stale
  verdict JSONs are tracked from an early force-commit; intentionally left.)
- **Env is read at process start** — after editing `.env` or the panel, restart
  `streamlit run`; the in-app Rerun won't pick it up.
- **This container's `cryptography` is broken** (`_cffi_backend`) — that's why
  `jwt` is imported lazily and offline paths avoid it. A clean
  `pip install -r requirements.txt` elsewhere is fine.
- **Validate UI changes headless** via `streamlit.testing.v1.AppTest`, not just
  "it serves 200".
- **Stub vs live:** `JURY_MODE=stub` (default) is fully offline; `live` needs the
  relevant API key(s); fetching uncached notes by ID needs Epic creds (live only).
- **Working style:** for anything beyond a small contained change, sketch/spec and
  get a 👍 before building.
