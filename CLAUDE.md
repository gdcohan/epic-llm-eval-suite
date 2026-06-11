# CLAUDE.md

Operational guide for working in this repo. Pair with `HANDOFF.md` (current
state, decisions, forward plan) and `ROADMAP.md` (build order). When state and
docs disagree, trust the code, then fix the doc.

## What this is

A POC that fetches clinical notes from Epic by ID via FHIR, persists them, and
runs an **LLM-as-jury** that scores a GenAI **summary against the totality of
its source notes** (per-dimension scores + verbatim source-linked findings +
harm tags), with human adjudication and calibration on top. Driver: evaluating
Epic GenAI summaries for a hospital system.

## Architecture (one line each)

- `api.py` — FastAPI backend (PRIMARY UI server): wraps `service.py`/`config.py`, serves the built SPA from `web/dist`.
- `web/` — React + Vite + TS + Tailwind frontend: Overview / Summary Explorer / Jury Config / Live Judge / Calibrate.
- `service.py` — the shared layer (CLI + web + legacy Streamlit): cases, judging, adjudication, authored findings, stats.
- `jury.py` / `dimensions.py` / `config.py` / `llm_providers.py` — panel runner; default dimension prompts + shared guidance/contract; editable persisted config (panel = enabled models × enabled personas); anthropic/openai/gemini/stub adapters.
- `epic_client.py` / `note_extractor.py` / `mock_client.py` — FHIR fetch (OAuth2/JWT, tolerant note resolver), note normalization, offline fixtures.
- `cases.py` / `persistence.py` — case manifests (summary ↔ source note IDs); local JSON under `data/` (gitignored).
- `probes.py` + `probes/` — omission-probe harness (regression suite for the comprehensiveness judge).
- `app.py` — LEGACY Streamlit UI (kept until the web UI is proven; same service layer).
- `main.py` — CLI (demo / discover / fetch / case / judge-case / run).

## Reproduce from a clean clone

```bash
pip install -r requirements.txt
cp .env.example .env                      # stub mode needs no keys
cd web && npm install && npm run build && cd ..
python examples/generate_demo_cases.py    # seed the 5 demo cases (data/ is gitignored)
uvicorn api:app --port 8000 --reload      # http://localhost:8000 — UI + API
```

That is the full demoable state, offline (`JURY_MODE=stub`, the default:
deterministic scores, no findings). For real judgments:

```bash
# .env: JURY_MODE=live + ANTHROPIC_API_KEY / GEMINI_API_KEY (and Epic creds
# only if fetching notes by ID). Panel/dimensions are editable in Jury Config.
JURY_MODE=live uvicorn api:app --port 8000 --reload
JURY_MODE=live python probes.py           # omission-probe suite (see below)
```

Frontend development: run uvicorn on **8000** and `cd web && npm run dev`, then
use **http://localhost:5173** (Vite proxies `/api`; hot reload). The 8000 URL
serves the last `npm run build`, which goes stale during development.

## Critical gotchas (each has bitten a session)

1. **Stale backend**: `npm run dev` hot-reloads ONLY the frontend. After
   pulling backend changes, restart uvicorn (or run with `--reload`). Symptom
   of a stale server: pydantic silently strips fields it doesn't know — e.g.
   saves that "don't persist".
2. **Stale frontend**: without `npm run dev`, the served UI is the last
   `npm run build`. Pulling source does not rebuild `web/dist/`.
3. **Config shadows code defaults**: `data/jury_config.json` (written by Jury
   Config saves) overrides `dimensions.py`/`config.py` defaults. After pulling
   a default-prompt change, "↺ reset dimensions" (or delete the file) or the
   new prompt never reaches the jury.
4. **`data/` is local and gitignored** — cases, notes, verdicts, adjudications,
   jury config. Nothing transfers between machines/containers; reseed with
   `python examples/generate_demo_cases.py`.
5. **Env is read at process start** — edit `.env`, restart uvicorn.
6. **Editable output contract is load-bearing** — must keep `score` /
   `synopsis` / `findings` keys and verbatim quotes, or scores/source-links
   break.

## Validation

- Frontend: `cd web && npm run build` (tsc strict + vite).
- Backend: stub-mode smoke via curl — `/api/panel`, `/api/cases`,
  `POST /api/cases/{id}/judge`, `/api/overview`, `/api/precision`.
- Jury plumbing: `python probes.py` runs end-to-end offline (stub warns and
  reports all-missed; that's expected).
- Legacy Streamlit is testable headless via `streamlit.testing.v1.AppTest`.

## Process / working style

- Develop on the session's designated `claude/...` branch; commit with the
  session link; do NOT open PRs or push elsewhere unless asked.
- For anything beyond a small contained change: **sketch/spec and get a 👍
  before building.**
- Backend + frontend changes ship together with a `web && npm run build` so
  the committed state is coherent (dist itself is gitignored).
