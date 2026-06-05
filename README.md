# Epic Note Fetcher + LLM-as-Jury (POC)

A quick proof-of-concept for pulling clinical **notes** out of Epic
programmatically via FHIR, persisting them faithfully, and then judging an
associated **GenAI summary** against the source note(s) with an LLM jury.

The input is a list of note IDs; the output is, per note: the full note text,
any linked/embedded content (addenda, etc.), the relevant metadata, and an
optional jury verdict scoring a candidate summary against the note.

> Forked from an earlier Epic SDOH agent — the OAuth2/JWT FHIR client is reused;
> the note-by-ID fetch, faithful persistence, and the jury are new.

## How it works

```
note ID(s) ──▶ EpicFHIRClient.resolve_document_reference()   (tolerant resolver)
            ──▶ note_extractor.extract_note()                 (text + addenda + metadata)
            ──▶ persistence.save_note()                       (data/notes/*.json)
candidate summary ─┐
                   └▶ jury.run_jury()                          (per-dimension panel)
            ──▶ persistence.save_verdict()                    (data/verdicts/*.json)
```

### The note identifier

A clinical "note" is a FHIR `DocumentReference`. Your list of IDs can take a few
shapes, and `resolve_document_reference()` handles all of them:

| Input shape | How it's resolved |
|---|---|
| FHIR logical ID (e.g. `eXyz123`) | direct `GET DocumentReference/{id}` |
| `DocumentReference/{id}` or absolute URL | stripped, then direct GET |
| `system\|value` identifier token | `DocumentReference?identifier=system\|value` |
| bare Epic-native value (DXN/note ID) | direct GET, then identifier search (incl. `EPIC_DOC_IDENTIFIER_SYSTEMS`) |

**Preference:** request FHIR logical IDs upstream if you can — cleanest path.
**Reality:** since Epic's GenAI summaries don't publicly document how they cite
source notes, the resolver is deliberately tolerant of whatever you get.

### What gets captured per note

Full text across **every** `content[].attachment` (inline base64 **and**
url-linked `Binary`, all formats), linked/embedded content via `relatesTo`
(addenda/appends resolved one level deep), and metadata: LOINC `type`, category,
`status`/`docStatus`, authors/authenticator, encounter, dates, security labels,
identifiers. The raw `DocumentReference` is retained too.

### Cases: linking a summary to its notes

A GenAI summary is drawn from **many** notes, so the unit of evaluation is a
**case** — one summary plus the set of source note IDs it came from
(`cases.py`, persisted at `data/cases/<case_id>.json`). The manifest references
notes by their `DocumentReference` ID (the same ID you fetch by), so notes live
once in `data/notes/` and are looked up on demand. When you have real Epic
GenAI summaries, the case manifest is exactly where you record their provenance
(which notes fed the summary). See `examples/cases/` for samples.

### The jury

A panel of **per-dimension jurists** (see `dimensions.py`) scores the candidate
summary against the **totality** of its source notes (concatenated oldest-first
with dated headers). The jury *requires* a summary. Defaults:

- **accuracy** — is every claim *faithful to the notes*? (grounding)
- **comprehensiveness** — does it capture all clinically significant info?
- **correctness** — is it *medically sound and internally coherent on its own
  terms*? A claim can be accurate (in the notes) yet incorrect (e.g.
  "atorvastatin for diabetes"); this juror uses clinical knowledge and does not
  treat "it's in the notes" as a defense.

**Recency reconciliation:** notes span time and may disagree. A shared guidance
clause tells jurors to treat the **more recent** note as authoritative when
notes conflict (unless it's clearly erroneous), so a summary reflecting the
current picture isn't penalized for "contradicting" a superseded older note.

Each dimension is judged by every panel member and aggregated: per-dimension
mean **plus disagreement** (score spread + an agreement label: unanimous / minor
/ split) and the jurors' flagged issues; the verdict also lists which dimensions
the jurors split on. For a real *jury* you want genuine diversity -- same-model
personas tend to agree, so set a **cross-vendor panel**:

```bash
JURY_MODE=live JURY_PANEL="anthropic:claude-sonnet-4-6,gemini:gemini-2.5-pro" \
  python main.py judge-case --case examples/cases/matera_flawed.json
```

Providers are pluggable (`llm_providers.py`): Anthropic, OpenAI, Gemini, and an
offline Stub ship today.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env        # fill in Epic creds + (for live jury) API keys
```

## Usage

```bash
# 1) Offline end-to-end on mock data — no creds or API keys needed:
python main.py demo

# 2) Don't have note IDs yet? List some from Epic's sandbox test patients:
python main.py discover

# 3) Fetch + persist real notes by ID:
python main.py fetch --ids <noteId1> <noteId2>
python main.py fetch --ids-file my_note_ids.txt

# 4) Create an eval case (summary + the notes it was drawn from), then judge it
#    against the TOTALITY of those notes:
python main.py case --id mycase --ids <noteId1> <noteId2> \
  --summary-text "..." --summary-source epic-genai
python main.py judge-case --case mycase

# 5) Fetch + judge a summary against all given notes in one shot:
python main.py run --ids <noteId1> <noteId2> --summary summary.txt

# Try the offline recency example (older 'severe' note superseded by a newer
# 'controlled' one) — set JURY_MODE=live for substantive scoring:
python main.py judge-case --case examples/cases/recency_demo.json --mock
```

`JURY_MODE=stub` (default) runs a deterministic offline jury so the pipeline is
demonstrable with zero external dependencies. Set `JURY_MODE=live` plus the
relevant API key for substantive judgments.

## UI (Streamlit)

```bash
streamlit run app.py            # JURY_MODE / JURY_PANEL from the environment
```

Populate five sample lifespan cases (annual-visit patients aged 12/25/40/65/80,
with summaries of deliberately varying fidelity to their notes — some faithful,
some with planted accuracy/comprehensiveness/correctness/reconciliation errors):

```bash
python examples/generate_demo_cases.py
```

A section selector across the top switches between **Overview**, **Summary
Explorer**, and (soon) Jury Config / Live Judge.

**Overview** — a cross-case dashboard: KPIs (cases, judged, avg overall, # with
issues, # juror splits), avg-score and issue-count bar charts by dimension, and a
sortable **case scorecard** (per-dimension scores, low values shaded red). The
*With issues* KPI filters the scorecard to just those cases, and selecting a row
opens that case in the Explorer.

**Summary Explorer** (V1, 3a) has the ingested summaries in the left sidebar and
a two-column body (independently scrollable):
- **col 1 — summary + judge synopsis**: the summary (with flagged spans
  highlighted), then per-dimension score, **disagreement** (agreement badge +
  each juror's score and one-line synopsis), and **structured, source-linked
  findings** — "summary said *X*, note *N* says *Y*" with a **↪ source** button
  that opens the cited note and highlights the span.
  Plus **✎ Adjudicate** — set a final per-dimension human score (e.g. resolve a
  2-vs-4 split as a 4). Adjudications are stored separately from the jury verdict,
  survive re-runs, and become the ground-truth labels for the future calibrator.
- **col 2 — reference notes**: each expandable to cleaned text (+ raw FHIR).

**➕ New summary** creates a case from a summary plus reference notes given as
Epic note IDs, **pasted note text**, or a mix — the pasted path is a first-class
escape hatch so the whole pipeline is demonstrable without FHIR. (A disabled
"fetch a summary by Epic ID" field marks the future provenance pathway.) In stub
mode the app is fully offline; `JURY_MODE=live` (+ keys) fetches notes by ID and
renders real judgments.

**Jury Config** (3b) — edit everything that defines the jury, persisted globally
to `data/jury_config.json` and applied on the next run: **dimensions** (add /
toggle / remove + prompts), **personas** (add / remove + temperature/text),
**models** (`provider:model`), and the shared **recency guidance** and **output
contract** (editable, with reset). The live panel is the **cross-product of
models × personas**; a preview shows the resulting juror count and calls-per-case.
**Show-the-prompt** previews the exact assembled juror prompt.

**Live Judge** (3c) — a scratchpad: paste or fetch notes, type a summary, and
**Judge** it live; edit the summary and re-judge to watch the scores move
(break-it-live). Nothing persists unless you **Save as case** (which drops it
into the Explorer).

## Files

| File | Role |
|---|---|
| `epic_client.py` | Epic FHIR client: OAuth2/JWT auth, tolerant note resolver, Binary fetch, discovery |
| `note_extractor.py` | `DocumentReference` → normalized note (text + addenda + metadata) |
| `persistence.py` | Local JSON persistence for notes and verdicts |
| `llm_providers.py` | Pluggable LLM providers (OpenAI / Anthropic / Stub) |
| `dimensions.py` | Jury dimensions (one prompt per jurist) + shared recency guidance |
| `jury.py` | Panel runner, multi-note aggregation + scoring |
| `cases.py` | Eval-case manifests (summary ↔ source note IDs) |
| `service.py` | Service layer for CLI/UI: list/create/judge cases, gather notes |
| `app.py` | Streamlit UI (Summary Explorer) |
| `mock_client.py`, `mock_data/` | Offline fixtures for the demo |
| `examples/cases/` | Sample eval cases (recency demo + MATERA faithful/flawed) |
| `main.py` | CLI |
