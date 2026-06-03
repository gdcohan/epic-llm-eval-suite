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

### The jury

A panel of **per-dimension jurists** (see `dimensions.py`) — `accuracy`,
`comprehensiveness`, `correctness` by default — each scores the **candidate
summary relative to the source notes**. The jury *requires* a summary; the
dimensions are only meaningful against one. Each dimension is judged by multiple
panel members (provider/model/temperature/persona) and averaged, then rolled up
to an overall score. Providers are pluggable (`llm_providers.py`): OpenAI and
Anthropic adapters ship today; spanning vendors is one config line.

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

# 4) Judge a persisted note against a candidate (GenAI) summary:
python main.py judge --note-file data/notes/<id>.json --summary summary.txt

# 5) Fetch + persist + judge in one shot:
python main.py run --ids <noteId> --summary summary.txt
```

`JURY_MODE=stub` (default) runs a deterministic offline jury so the pipeline is
demonstrable with zero external dependencies. Set `JURY_MODE=live` plus the
relevant API key for substantive judgments.

## Files

| File | Role |
|---|---|
| `epic_client.py` | Epic FHIR client: OAuth2/JWT auth, tolerant note resolver, Binary fetch, discovery |
| `note_extractor.py` | `DocumentReference` → normalized note (text + addenda + metadata) |
| `persistence.py` | Local JSON persistence for notes and verdicts |
| `llm_providers.py` | Pluggable LLM providers (OpenAI / Anthropic / Stub) |
| `dimensions.py` | Jury dimensions (one prompt per jurist) |
| `jury.py` | Panel runner + aggregation |
| `mock_client.py`, `mock_data/` | Offline fixtures for the demo |
| `main.py` | CLI |
