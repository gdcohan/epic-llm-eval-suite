# Roadmap

Living plan for the Epic note-fetcher + LLM-as-jury POC. Build order is
sequential — each step assumes the previous is done.

## Build order

### 1. Live smoke test + calibration  · *needs API keys*
Run the example cases (`matera_faithful` / `matera_flawed`, `recency_demo`)
through the **real** panel. Confirm: scores separate good from bad, rationales
name the planted errors, the recency clause holds. Tune the 1–5 scale anchoring,
prompt wording, and **lock the panel** (which / how many models).
*Deliverable:* a jury we trust enough to build a UI around.

### 2. Jury diversity + disagreement surfacing  · *offline-buildable*
Informed by calibration: finalize the panel (single-provider personas vs. true
multi-vendor), and compute **per-dimension disagreement** (score spread /
agreement across jurors) + aggregated flagged issues.
*Why here:* it's the data the UI's verdict view renders.

### 3. UI V1 (Streamlit)  · *offline-buildable, demoable*

*(Built: 3a Explorer, Overview dashboard, adjudication, structured/source-linked verdicts; 3b Jury Config; 3c Live Judge. UI V1 complete.)*
- **3a. Summary Explorer** — list ingested summaries (cases) → pick one → jury
  eval + disagreement + list of reference notes + note viewer.
- **3b. Jury config** — add / toggle / remove dimensions, edit prompts,
  configure the panel (doubles as the calibration cockpit).
- **3c. Live ad-hoc judging** — input a summary, ingest notes via **paste AND
  fetch-by-ID**, judge, **break-it-live**.
*Deliverable:* the coworker demo.

### 4. Calibration / tuning (near term)  · *needs API keys to run*

A **labeled example = a case + its human adjudication** (both already exist), so
the benchmark is just the set of adjudicated cases. Two ways to create them:
- **De novo** — author a summary + notes + per-dimension human scores in one
  form, without running the jury.
- **Via live judging** — judge in the scratchpad, adjudicate the result, and Save
  as a labeled example (Live Judge gains adjudication controls + save).

**Measurement layer** (a new **Calibrate** tab): run the current jury config over
all labeled examples and report jury-vs-human agreement per dimension (mean
delta, where it splits) + a ranked, drill-into list of the biggest disagreements.
"Is the jury any good?"

**Manual tuning loop** (bucket 1): a pin / before-after **compare** in Live Judge
so a prompt/panel change visibly moves the scores on an example.

Higher rungs are later (they need more labeled volume): few-shot anchoring with
adjudicated examples, score recalibration (learn jury→human offsets), and
LLM-proposed prompt edits. Train/test split matters once examples feed the prompt.

*Enabler to decide:* named config snapshots/experiments (so verdicts know which
config produced them) for honest A/B and measurement.

## Future (punted)

- ~~**Citations (V2)**~~ — *pulled forward into 3a*: jurors emit structured
  findings (score + synopsis + issues with verbatim summary/note quotes +
  note_id), source-linked and highlighted in the Explorer.
- **Jury calibrator screen** — human-in-the-loop on top of the validation
  harness: review known examples, see jury scores, adjudicate / overrule / score.
- **Synthetic summary generation** — LLM summarizer + deliberate error-injection
  to produce labeled candidates at volume (feeds the harness; previews the real
  workflow).
- **Hardening** — prompt-injection defense (note text is untrusted), prompt
  caching for the shared notes block, cost / latency, structured-output robustness.
- **Production readiness** — ingest real Epic GenAI summaries + their provenance;
  PHI / BAA; non-sandbox org connection.
