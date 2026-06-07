# Handoff / Context

Continuity notes so a new session (or a new contributor) can pick up without
re-deriving everything. Pair this with `README.md` (how to run) and `ROADMAP.md`
(what's next).

**Working branch:** `claude/dreamy-wright-Qe8jN` (develop + push here).

---

## What this project is

A quick-and-dirty POC, forked from an Epic *SDOH agent* but repurposed:

1. **Fetch clinical notes from Epic by ID via FHIR** (`DocumentReference` → `Binary`),
2. **persist** them with full text + linked/embedded content + metadata,
3. run an **LLM-as-jury** that evaluates a **GenAI summary against the totality of
   its source notes**, producing per-dimension scores + structured, source-linked
   findings, and
4. a **Streamlit UI** to explore, configure, live-judge, and calibrate it.

The real-world driver: evaluating the source notes behind **Epic GenAI summaries**.
We don't yet know how Epic exposes summary→source-note provenance, so the pipeline
is built to not depend on it (pasted-notes escape hatch everywhere).

---

## Architecture (module map)

| File | Role |
|---|---|
| `epic_client.py` | Epic FHIR client: OAuth2/JWT (SMART backend), **tolerant note resolver**, Binary fetch, patient discovery. `jwt` imported lazily. |
| `note_extractor.py` | `DocumentReference` → normalized note: markup-stripped text, dedup of format-duplicate content, `relatesTo` addenda, metadata. `make_manual_note()` builds the same shape from pasted text. |
| `persistence.py` | Local JSON: notes / verdicts / adjudications (all under `data/`, gitignored). |
| `cases.py` | Eval-case manifest = summary + `source_note_ids`. |
| `config.py` | Editable jury config (dimensions / personas / models / source_guidance / output_contract), persisted to `data/jury_config.json`; falls back to code defaults. **Panel = models × personas.** |
| `dimensions.py` | Default dimensions, `SOURCE_GUIDANCE` (reconciliation), `OUTPUT_CONTRACT` (findings schema incl. harm). |
| `jury.py` | `run_jury(notes, summary, dims, panel, source_guidance, output_contract)`: aggregates source notes chronologically, runs each (dimension × juror), per-dimension stats + disagreement + findings. |
| `llm_providers.py` | Pluggable providers: anthropic / openai / **gemini** / stub. |
| `service.py` | The layer the CLI **and** UI share: list/create/judge cases, gather notes, adjudication (dimension + **finding-level**), `overview_stats`, `precision_stats`, `judge_adhoc`. |
| `app.py` | Streamlit UI (Overview / Summary Explorer / Jury Config / Live Judge / Calibrate). |
| `main.py` | CLI (demo / fetch / discover / case / judge-case / run). |
| `mock_client.py`, `mock_data/` | Offline FHIR fixtures for `python main.py demo`. |
| `examples/cases/*.json`, `examples/generate_demo_cases.py` | Sample + 5 lifespan demo cases. |

---

## Core concepts

- **Case** = a candidate summary + the source note IDs it was drawn from.
- **Verdict** = per-dimension `mean_score` + disagreement (spread / agreement) + a
  flat list of **findings**.
- **Finding** (structured citation) = `{type: issue|support, summary_quote,
  note_quote, note_id, explanation, member, harm_category, harm_severity}`. Quotes
  are **verbatim** so the UI can locate + highlight them.
- **Dimensions** (default): **accuracy** (faithful to notes), **comprehensiveness**
  (captures all clinically significant info; "could change management" heuristic),
  **correctness** (intrinsically sound/coherent — judged *independently* of the notes).
- **Panel** = cross-product of **models × personas** (default personas: strict,
  balanced). Stub mode = one juror per persona, offline.
- **Reconciliation guidance** (shared): how jurors resolve conflicting notes
  (temporal/superseded, status/certainty, source authority, specificity, repeated
  measures, clear-error-conservative) + an unresolved→uncertainty fallback.
- **Harm matrix** (V1): each issue finding tagged inline with `harm_category` +
  `harm_severity` (low/moderate/severe). Surfaced on Overview at the **case level**.
- **Adjudication** = human ground truth. **Finding-level** (✓ valid / ✗ false
  alarm) is primary; a thin per-dimension score override is secondary.

---

## Key decisions (so they're not relitigated)

- **Note identifier:** prefer the FHIR **DocumentReference logical ID**; the
  resolver also handles `system|value` tokens and bare Epic-native IDs (DXN/CSN),
  which need the FHIR identifier *system* OID (env `EPIC_DOC_IDENTIFIER_SYSTEMS`).
- **Jury judges the summary vs. the TOTALITY of notes**, not one note.
- **correctness ≠ accuracy:** a claim can be faithful to the notes yet incorrect
  (e.g. "statin for diabetes"), and vice-versa.
- **Output contract is editable but load-bearing** — must keep `score` / `synopsis`
  / `findings`, or scores/links break.
- **Calibration unit = a finding** (not a whole case — too noisy). **Precision
  first**; **recall** (authoring missed issues) is the agreed next step.
  **V1 labels per juror** (no span dedup — that's V2; we avoided fragile span
  matching).
- **Harm:** V1 inline per-finding (severity rated *independently* of juror
  leniency). V2 = dedicated harm pass + likelihood axis (severity × likelihood) +
  per-summary risk roll-up + harm-weighted calibration.
- **Config A/B experiments** = mid-term (named config snapshots).
- **Calibration created two ways:** de novo authoring + harvested from live judging.

---

## Current state — and the BIG gap

Everything below is **validated in stub mode** (offline, deterministic) and via
Streamlit `AppTest`. **No `JURY_MODE=live` run has happened yet.** So:

- Real findings, harm badges, the Calibrate precision numbers, and the Overview
  harm matrix are all **empty/meaningless until a live run** (stub emits no findings).
- **The single highest-value next action is a live shakedown** (`JURY_MODE=live`
  with Claude + Gemini) across the 5 demo cases — to confirm the prompts behave,
  the planted errors get caught, verbatim highlights land, and harm/severity is
  sane. It doubles as the demo rehearsal.

What IS proven live: **fetching real notes from the Epic public sandbox**
(Jason Argonaut), incl. the DocumentReference→Binary hop and markup/dedup cleanup.

**Built:** fetch + extraction; multi-vendor jury + disagreement; structured
source-linked findings; reconciliation framework; harm matrix V1; full UI
(Overview w/ harm, Explorer w/ adjudication + finding-labeling, Jury Config, Live
Judge, Calibrate precision); 5 demo cases.

**Not built yet:** live calibration run; **recall** authoring; **de novo probe**
authoring; Live-Judge **pin/compare** tuning loop; harm **roll-up score / V2 pass**;
A/B config experiments; synthetic summary generation; prod/PHI hardening.

---

## Conventions & gotchas

- **`data/` is gitignored** — cases, verdicts, notes, adjudications, and
  `jury_config.json` are **local to each container**. Nothing there transfers
  across sessions; re-run `python examples/generate_demo_cases.py` to reseed.
  (Two stale verdict JSONs are tracked from an early force-commit; intentionally
  left.)
- **Env is read at process start** — after editing `.env` or the panel, **restart**
  `streamlit run`; the in-app Rerun won't pick it up.
- **Stub vs live:** `JURY_MODE=stub` (default) is fully offline; `live` needs the
  relevant API key(s); fetching uncached notes by ID needs Epic creds (live only).
- **Validation:** the app is testable headless via `streamlit.testing.v1.AppTest`
  (used throughout instead of just "it serves 200").
- **This dev container's `cryptography` is broken** (`_cffi_backend`); that's why
  `jwt` import is lazy and offline paths avoid it. A clean `pip install` elsewhere
  is fine.
- **Process:** develop on the working branch; commit messages end with the session
  link; do **not** open PRs or push elsewhere unless asked.
- **Working style the user prefers:** for anything beyond a small contained change,
  **sketch/spec and get a 👍 before building.** (Earlier in this project a few
  features got built ahead of confirmation — avoid that.)
