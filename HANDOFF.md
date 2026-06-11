# Handoff / Context

Continuity notes so a new session (or a new contributor) can pick up without
re-deriving everything. Pair this with `README.md` (how to run) and `ROADMAP.md`
(what's next).

**Working branch:** `claude/gracious-mendel-u4go4n` (develop + push here).

---

## What this project is

A quick-and-dirty POC, forked from an Epic *SDOH agent* but repurposed:

1. **Fetch clinical notes from Epic by ID via FHIR** (`DocumentReference` → `Binary`),
2. **persist** them with full text + linked/embedded content + metadata,
3. run an **LLM-as-jury** that evaluates a **GenAI summary against the totality of
   its source notes**, producing per-dimension scores + structured, source-linked
   findings, and
4. a **web UI** (FastAPI `api.py` + React `web/` — primary; Streamlit `app.py` is
   the legacy fallback) to explore, configure, live-judge, and calibrate it.

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
| `api.py` | FastAPI backend for the web UI: thin HTTP wrapper over service/config, enriches verdict findings with adjudication keys, serves the built SPA from `web/dist`. |
| `web/` | React + Vite + TypeScript + Tailwind frontend — the PRIMARY UI (same five sections as the Streamlit app, feature parity). `npm run build` then serve via uvicorn; `npm run dev` proxies `/api` to :8000. |
| `app.py` | LEGACY Streamlit UI (Overview / Summary Explorer / Jury Config / Live Judge / Calibrate) — kept until the web UI is proven, then delete. |
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
- **Comprehensiveness judge**: rewritten (June 2026) to be omission-only —
  notes→summary direction, internal two-pass instruction, explicit "do NOT do
  accuracy's job" clause (it was acting as a second accuracy judge). Escalation
  path if probes show misses: emit the fact inventory as structured output
  (needs a jury.py passthrough), or enable extended thinking for the Anthropic
  juror. The Anthropic (no thinking) vs Gemini 2.5 Pro (thinks by default)
  split on the panel is a natural A/B for whether the scratchpad matters.
- **Human-flagged missed issues** (`authored_findings` in the adjudication,
  separate from `finding_labels`): assertions about the case, not labels on
  jury output — the future recall denominator. UI: "✋ flag missed issue" per
  dimension in the Explorer. Quantified recall deliberately deferred.
- **Omission probes** (`probes/` + `python probes.py`): planted single-fact
  omission variants + term-matched caught/missed report per juror — the
  regression suite for judge-prompt tuning. Run live; stub emits no findings.
- **Harm:** V1 inline per-finding (severity rated *independently* of juror
  leniency). V2 = dedicated harm pass + likelihood axis (severity × likelihood) +
  per-summary risk roll-up + harm-weighted calibration.
- **Config A/B experiments** = mid-term (named config snapshots).
- **Calibration created two ways:** de novo authoring + harvested from live judging.

---

## Current state

**The web UI is primary** (June 2026 rebuild): `api.py` (FastAPI over the same
service layer) + `web/` (React/Vite/TS/Tailwind), all five sections at parity
with — and now beyond — the legacy Streamlit app. UI niceties added since the
rebuild: browser-history routing (`/explorer/<case>` deep links; Back unwinds
navigation), collapsible case sidebar / reference-notes column / dimension
cards / issues zone (issues start collapsed), Overview KPI + harm-matrix cells
navigate straight to the Explorer (anchored picker when several cases match),
enable/disable toggles for dimensions AND personas AND models (explicit 💾
save; panel = enabled models × enabled personas), header juror list stays in
sync with config saves. Reproduction from a clean clone: see `CLAUDE.md`.

**Live runs have started.** The user has run the live jury (Claude + Gemini).
First live lesson already fixed: juror JSON was truncated at the Anthropic
adapter's old `max_tokens=1500` → now 8000 + explicit truncation error + one
retry on unparseable-JSON responses. No systematic live calibration pass has
been recorded yet.

**Built:** fetch + extraction; multi-vendor jury + disagreement; structured
source-linked findings; reconciliation framework; harm matrix V1; full web UI
(Overview w/ harm, Explorer w/ adjudication + finding-labeling + ✋ authored
missed issues, Jury Config, Live Judge, Calibrate precision + authored counts);
5 demo cases; **omission-probe harness** (`probes.py`); **rewritten
omission-only comprehensiveness judge**.

**Not built yet:** recall/F1 quantification (deliberately deferred — see
forward plan below); Live-Judge **pin/compare** tuning loop; harm **roll-up
score / V2 pass**; A/B config experiments; synthetic summary generation;
prod/PHI hardening; Streamlit retirement.

---

## Forward plan: comprehensiveness → recall (agreed with the user)

The agreed sequencing — get comprehensiveness good first, quantify recall later:

1. **Now (built):** omission-only comprehensiveness prompt (internal two-pass,
   notes→summary, accuracy firewall) + ✋ human-flagged missed issues
   (`authored_findings`) + the omission-probe suite.
2. **Next action:** a live probe run (`JURY_MODE=live python probes.py`).
   The panel split is a deliberate A/B: the Anthropic juror runs WITHOUT
   extended thinking (no internal scratchpad — the "internally do two passes"
   instruction is aspirational there) while Gemini 2.5 Pro thinks by default.
   Per-juror probe recall tells us whether the scratchpad matters and guides
   model choice.
3. **Escalation if probes show misses** (in order): (a) make the judge EMIT the
   fact inventory as structured output (extra `inventory` key; needs a small
   `jury.py` passthrough since it keeps only score/synopsis/findings — buys
   reliability for non-thinking models AND auditability of which facts were
   enumerated vs wrongly marked present); (b) enable extended thinking for the
   Anthropic juror (reliability without auditability); (c) true two-call
   scaffold (extract checklist, then check coverage; score = coverage ratio).
4. **Recall quantification, eventually, in three layers:**
   - *Panel-union recall* (free): per-juror recall against the union of
     human-validated findings across the panel — falls out of existing labels.
   - *Probe recall* (controlled): caught/planted from the probe suite,
     stratified by harm severity; exact ground truth, but synthetic
     distribution.
   - *Observed recall* (gold): validated ÷ (validated + authored-missed) from
     `authored_findings` — biased upward (anchoring) but measures reality; the
     storage is already shaped for this (assertions, separate from labels).

---

## Conventions & gotchas

- **`data/` is gitignored** — cases, verdicts, notes, adjudications, and
  `jury_config.json` are **local to each container**. Nothing there transfers
  across sessions; re-run `python examples/generate_demo_cases.py` to reseed.
  (Two stale verdict JSONs are tracked from an early force-commit; intentionally
  left.)
- **Env is read at process start** — after editing `.env`, **restart** the
  server (uvicorn or streamlit).
- **Stale-server trap**: `npm run dev` reloads only the frontend; after pulling
  backend changes restart uvicorn (or run `--reload`). A stale server's pydantic
  models silently strip new fields — looks like "saves don't persist".
- **Config shadowing**: `data/jury_config.json` overrides code defaults; after a
  default-prompt change, reset dimensions in Jury Config or the jury never sees it.
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
