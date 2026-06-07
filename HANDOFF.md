# Handoff

Transition notes only — what a new session needs to pick up *right now*. Anything
durable lives in `README.md` (how it works + module map + concepts) and
`ROADMAP.md` (plan + design notes + key decisions).

**Working branch:** `claude/brave-meitner-2Tqc2` (develop + push here; no PRs unless asked).

## Current state / in-flight

Everything is **validated in stub mode** (offline, deterministic) and via Streamlit
`AppTest`. **No `JURY_MODE=live` run has happened yet** — so real findings, harm
badges, Calibrate precision, and the Overview harm matrix are **empty/meaningless
until a live run** (stub emits no findings).

- **Highest-value next action:** a live shakedown (`JURY_MODE=live`, Claude +
  Gemini) across the 5 demo cases — confirm prompts behave, planted errors get
  caught, verbatim highlights land, harm/severity is sane. Doubles as the demo
  rehearsal. (See ROADMAP §1.)
- **Proven live:** fetching real notes from the Epic public sandbox (Jason
  Argonaut), incl. the DocumentReference→Binary hop + markup/dedup cleanup.

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
