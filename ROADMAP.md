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

*(Core built: finding-level ✓/✗ labeling in the Explorer verdict + a Calibrate
tab with per-dimension precision and a false-alarm drill-down. Remaining: de novo
probe authoring, then recall.)*

**The unit of calibration is a finding, not a whole case** (a full-case score
over many notes is noisy and unattributable). A labeled example = a jury finding
(dimension + summary span + note span) + a human label (valid issue / false
alarm). The full case stays the *demo* unit; findings are the calibration signal
-- atomic and attributable.

Create labeled findings two ways:
- **Via judging** — the human thumbs-up/down each jury finding in the verdict
  (primary adjudication; built in the Explorer — Live Judge labeling is a follow-up).
- **De novo** — author a minimal probe: one dimension, a summary snippet, a note
  snippet, and the gold call.

**Measurement** (a new **Calibrate** tab), precision-first: per-dimension
precision (of the jury's flagged findings, how many the human validated) + drill
into the false alarms. A thin per-dimension score adjudication remains as a
secondary roll-up.

*Next step after the core:* **recall (finding-level)** — a UI to author the
issues the jury *missed* (false negatives), enabling recall/F1, not just
precision.
- **Unit:** same atomic finding (dimension + summary span + note span), but
  human-originated — overlaps with de-novo probe authoring.
- **Metric:** recall = gold issues caught ÷ total gold issues.
- **V1 (buildable now, no new primitive):** treat recall labels like precision
  labels — tied to a specific verdict. The human authors "the jury missed X here"
  (pick dimension + quote the span); it counts as a false negative for *that*
  run. No semantic matching required. Limitation: the label doesn't auto-carry to
  a re-judge (same content-key orphaning as precision labels).
- **Richer (later):** to credit a re-run where the jury *does* surface a
  previously "missed" issue, you need to match jury findings ↔ gold findings (span
  overlap / semantic match) — i.e. the finding-matching / span-grouping primitive
  punted to V2 dedup. That's the real unlock for durable recall.
- **Authoring UX is the work:** unlike a thumbs-down on an existing finding,
  there's no span to click — the human must select/quote the missed span and tag
  it.

**Manual tuning loop** (bucket 1): a pin / before-after **compare** in Live Judge
so a prompt/panel change visibly moves the result on an example.

Higher rungs are later (they need more labeled volume): few-shot anchoring with
adjudicated examples, score recalibration (learn jury→human offsets), and
LLM-proposed prompt edits. Train/test split matters once examples feed the prompt.

**Few-shot anchoring (detail):** inject scored exemplars into the juror prompts to
calibrate behavior toward the human ("an expert rated this span a false alarm / a
severe accuracy issue because…"), per dimension.
- **V1 (cheap precursor, no benchmark dependency):** hand-author a few canonical
  rubric exemplars directly in the prompt. They're not eval data, so there's **no
  leakage and no volume requirement** — it's prompt engineering with worked
  examples. Wires into the existing editable output contract / show-the-prompt.
- **Richer (later):** harvest exemplars from the adjudicated benchmark (the
  labeled findings). More powerful, but blocked on two things: (1) **leakage** —
  anchors must come from a held-out split, never the eval set; (2) **volume** — a
  handful of cases isn't enough to anchor *and* evaluate (the main argument for the
  synthetic-summary generator). Open design Qs: which examples to select (false
  alarms? hardest/most-disputed? balanced?), how many, exemplar format,
  per-dimension wiring.
- **Dependency order:** V1 anytime; the harvested version needs synthetic
  summaries + a train/test split first.

*Mid-term:* true A/B config experiments — named config snapshots so verdicts
record which config produced them; compare two configs over the benchmark.

## Future (punted)

- **Harm matrix** — *V1 built*: each issue finding is tagged inline with a
  clinical `harm_category` and `harm_severity` (low/moderate/severe), shown as a
  badge. *V2*: a dedicated harm pass (decouple severity from the flagging
  juror's leniency), a likelihood axis (severity × likelihood risk matrix), and
  roll-up to a per-summary risk heatmap / score + harm-weighted calibration.

- ~~**Citations (V2)**~~ — *pulled forward into 3a*: jurors emit structured
  findings (score + synopsis + issues with verbatim summary/note quotes +
  note_id), source-linked and highlighted in the Explorer.
- ~~**Jury calibrator screen**~~ — *folded into #4 (Calibrate tab + finding-level
  adjudication).*
- **Synthetic summary generation** — LLM summarizer + deliberate error-injection
  to produce labeled candidates at volume (feeds the harness; previews the real
  workflow).
- **Hardening** — prompt-injection defense (note text is untrusted), prompt
  caching for the shared notes block, cost / latency, structured-output robustness.
- **Production readiness** — ingest real Epic GenAI summaries + their provenance;
  PHI / BAA; non-sandbox org connection.
