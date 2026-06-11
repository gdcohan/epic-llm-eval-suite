"""FastAPI backend for the GenAI Eval Harness web UI.

A thin HTTP wrapper over service.py / config.py — the same layer the CLI and
Streamlit app use, so all three front-ends stay in lockstep.

Run (dev):   uvicorn api:app --reload --port 8000
             (plus `npm run dev` in web/ — Vite proxies /api here)
Run (prod):  cd web && npm run build, then uvicorn api:app --port 8000
             (the built SPA in web/dist is served at /)

Jury mode follows the environment (JURY_MODE=stub default, or live + keys).
"""

import os

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
import jury
import rubric_advisor
import service

app = FastAPI(title="GenAI Eval Harness API")

WEB_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "dist")


# ------------------------------------------------------------- request models
class PastedNote(BaseModel):
    text: str
    type: str | None = None
    date: str | None = None


class CreateCaseBody(BaseModel):
    summary_text: str
    case_id: str | None = None
    note_ids: list[str] = []
    pasted_notes: list[PastedNote] = []


class JudgeAdhocBody(BaseModel):
    summary_text: str
    note_ids: list[str] = []
    pasted_notes: list[PastedNote] = []


class FindingLabelBody(BaseModel):
    dimension: str
    member: str | None = None
    summary_quote: str | None = None
    note_quote: str | None = None
    note_id: str | None = None
    label: str | None = None  # 'valid' | 'false_alarm' | None to clear
    explanation: str | None = None  # the finding's explanation (advisor context)
    reason: str | None = None  # rejection taxonomy (false alarms)
    note: str | None = None  # free-text 'teach the jury'
    corrected_harm_category: str | None = None
    corrected_harm_severity: str | None = None


class ExemplarBody(BaseModel):
    dimension: str
    kind: str  # 'valid' | 'false_alarm' | 'missed'
    summary_quote: str | None = None
    note_quote: str | None = None
    explanation: str | None = None
    reason: str | None = None
    teaching_note: str | None = None
    harm_category: str | None = None
    harm_severity: str | None = None


class AuthoredFindingBody(BaseModel):
    dimension: str
    explanation: str = ""
    note_quote: str | None = None
    note_id: str | None = None
    harm_category: str | None = None
    harm_severity: str | None = None
    author: str = ""


class DimensionAdjudicationBody(BaseModel):
    dimension: str
    score: int | None = None  # None clears the override
    rationale: str = ""
    adjudicator: str = ""


class DimensionConfig(BaseModel):
    name: str
    description: str = ""
    prompt: str = ""
    scale: str = "1-5"
    enabled: bool = True


class PersonaConfig(BaseModel):
    name: str
    temperature: float = 0.2
    text: str = ""
    enabled: bool = True


class ModelConfig(BaseModel):
    provider: str
    model: str = ""
    enabled: bool = True


class SharedTextBody(BaseModel):
    text: str


def _with_finding_keys(verdict):
    """Tag each finding with its stable adjudication key so the UI can match
    labels without re-implementing the hash."""
    if not verdict:
        return verdict
    for d in verdict.get("dimensions", []):
        for f in d.get("findings", []):
            f["key"] = service.finding_key(
                d.get("dimension"), f.get("member"), f.get("summary_quote"), f.get("note_quote")
            )
    return verdict


# -------------------------------------------------------------------- meta
@app.get("/api/panel")
def panel():
    info = service.panel_info()
    members = config.active_panel()
    n_dims = len(config.active_dimensions())
    return {
        "mode": info["mode"],
        "members": info["members"],
        "panel": [m.name for m in members],
        "n_dimensions": n_dims,
        "calls_per_case": len(members) * n_dims,
    }


@app.get("/api/overview")
def overview():
    stats = service.overview_stats()
    stats["harm_categories"] = service.HARM_CATEGORIES
    return stats


@app.get("/api/precision")
def precision():
    return service.precision_stats()


# -------------------------------------------------------------------- cases
@app.get("/api/cases")
def list_cases():
    return service.list_cases()


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    try:
        case = service.load_case(case_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"No case '{case_id}'")
    notes, missing = service.case_notes(case)
    return {
        "case": case,
        "notes": notes,
        "missing_note_ids": missing,
        "verdict": _with_finding_keys(service.load_verdict(case_id)),
        "adjudication": service.get_adjudication(case_id),
    }


@app.post("/api/cases")
def create_case(body: CreateCaseBody):
    try:
        case = service.create_case(
            summary_text=body.summary_text,
            case_id=body.case_id,
            note_ids=body.note_ids,
            pasted_notes=[p.model_dump() for p in body.pasted_notes],
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return case


@app.post("/api/cases/{case_id}/judge")
def judge_case(case_id: str):
    try:
        case = service.load_case(case_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"No case '{case_id}'")
    try:
        verdict, missing = service.judge_case(case)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"verdict": _with_finding_keys(verdict), "missing_note_ids": missing}


@app.post("/api/judge-adhoc")
def judge_adhoc(body: JudgeAdhocBody):
    try:
        verdict, notes, missing = service.judge_adhoc(
            body.summary_text,
            note_ids=body.note_ids,
            pasted_notes=[p.model_dump() for p in body.pasted_notes],
        )
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"verdict": verdict, "notes": notes, "missing_note_ids": missing}


# ------------------------------------------------------------- adjudication
@app.post("/api/cases/{case_id}/finding-label")
def set_finding_label(case_id: str, body: FindingLabelBody, background_tasks: BackgroundTasks):
    key = service.finding_key(body.dimension, body.member, body.summary_quote, body.note_quote)
    meta = {
        "dimension": body.dimension,
        "member": body.member,
        "summary_quote": body.summary_quote,
        "note_quote": body.note_quote,
        "note_id": body.note_id,
    }
    adj = service.set_finding_label(
        case_id, key, body.label, meta, reason=body.reason, note=body.note,
        corrected_harm_category=body.corrected_harm_category,
        corrected_harm_severity=body.corrected_harm_severity,
    )
    # A rejection-with-why or a harm correction may reveal a rubric principle —
    # let the advisor consider it (async, live mode only, never blocks).
    corrected = body.corrected_harm_category or body.corrected_harm_severity
    if body.label == "false_alarm" or (body.label == "valid" and corrected):
        background_tasks.add_task(rubric_advisor.consider_example, {
            "kind": "false_alarm" if body.label == "false_alarm" else "harm_correction",
            "case_id": case_id,
            "dimension": body.dimension,
            "summary_quote": body.summary_quote,
            "note_quote": body.note_quote,
            "finding_explanation": body.explanation,
            "reviewer_reason": body.reason,
            "reviewer_note": body.note,
            "original_harm_category": None,
            "corrected_harm_category": body.corrected_harm_category,
            "corrected_harm_severity": body.corrected_harm_severity,
        })
    return adj


@app.post("/api/cases/{case_id}/authored-finding")
def add_authored_finding(case_id: str, body: AuthoredFindingBody, background_tasks: BackgroundTasks):
    try:
        adj = service.add_authored_finding(
            case_id, body.dimension, body.explanation, note_quote=body.note_quote,
            note_id=body.note_id, harm_category=body.harm_category,
            harm_severity=body.harm_severity, author=body.author,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    background_tasks.add_task(rubric_advisor.consider_example, {
        "kind": "missed_issue",
        "case_id": case_id,
        "dimension": body.dimension,
        "note_quote": body.note_quote,
        "reviewer_note": body.explanation,
        "harm_category": body.harm_category,
        "harm_severity": body.harm_severity,
    })
    return adj


@app.delete("/api/cases/{case_id}/authored-finding/{finding_id}")
def remove_authored_finding(case_id: str, finding_id: str):
    return service.remove_authored_finding(case_id, finding_id)


@app.post("/api/cases/{case_id}/adjudicate-dimension")
def adjudicate_dimension(case_id: str, body: DimensionAdjudicationBody):
    return service.set_dimension_adjudication(
        case_id, body.dimension, body.score, body.rationale, body.adjudicator
    )


# -------------------------------------------------------------------- config
@app.get("/api/config")
def get_config():
    return {
        "dimensions": config.all_dimension_configs(),
        "personas": config.all_personas(),
        "models": config.all_models(),
        "source_guidance": config.active_source_guidance(),
        "output_contract": config.active_output_contract(),
        "review_rubric": config.active_review_rubric(),
        "exemplars": config.all_exemplars(),
        "exemplar_cap": config.EXEMPLAR_CAP_PER_DIMENSION,
    }


@app.put("/api/config/review-rubric")
def save_review_rubric(body: SharedTextBody):
    config.save_review_rubric(body.text)
    return {"ok": True}


@app.delete("/api/config/review-rubric")
def reset_review_rubric():
    config.reset_review_rubric()
    return {"text": config.active_review_rubric()}


# --------------------------------------------------------- rubric proposals
@app.get("/api/rubric-proposals")
def list_rubric_proposals():
    return rubric_advisor.list_proposals()


@app.post("/api/rubric-proposals/{proposal_id}/resolve")
def resolve_rubric_proposal(proposal_id: str, body: dict):
    try:
        proposals = rubric_advisor.resolve_proposal(proposal_id, bool(body.get("accept")))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"proposals": proposals, "review_rubric": config.active_review_rubric()}


# ---------------------------------------------------------------- exemplars
@app.post("/api/exemplars")
def add_exemplar(body: ExemplarBody):
    try:
        return config.add_exemplar(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.delete("/api/exemplars/{exemplar_id}")
def remove_exemplar(exemplar_id: str):
    return config.remove_exemplar(exemplar_id)


@app.put("/api/config/dimensions")
def save_dimensions(dims: list[DimensionConfig]):
    config.save_dimensions([d.model_dump() for d in dims])
    return {"active": len(config.active_dimensions())}


@app.delete("/api/config/dimensions")
def reset_dimensions():
    config.reset_dimensions()
    return config.all_dimension_configs()


@app.put("/api/config/personas")
def save_personas(personas: list[PersonaConfig]):
    config.save_personas([p.model_dump() for p in personas])
    return {"ok": True}


@app.delete("/api/config/personas")
def reset_personas():
    config.reset_personas()
    return config.all_personas()


@app.put("/api/config/models")
def save_models(models: list[ModelConfig]):
    config.save_models([m.model_dump() for m in models])
    return {"ok": True}


@app.delete("/api/config/models")
def reset_models():
    config.reset_models()
    return config.all_models()


@app.put("/api/config/source-guidance")
def save_source_guidance(body: SharedTextBody):
    config.save_source_guidance(body.text)
    return {"ok": True}


@app.delete("/api/config/source-guidance")
def reset_source_guidance():
    config.reset_source_guidance()
    return {"text": config.active_source_guidance()}


@app.put("/api/config/output-contract")
def save_output_contract(body: SharedTextBody):
    config.save_output_contract(body.text)
    return {"ok": True}


@app.delete("/api/config/output-contract")
def reset_output_contract():
    config.reset_output_contract()
    return {"text": config.active_output_contract()}


@app.get("/api/config/prompt-preview")
def prompt_preview(dimension: str, persona: str | None = None):
    """The exact assembled system prompt one juror would get (saved config)."""
    dims = config.active_dimensions()
    d = next((x for x in dims if x.name == dimension), None)
    if not d:
        raise HTTPException(status_code=404, detail=f"No active dimension '{dimension}'")
    persona_text = ""
    if persona:
        p = next((p for p in config.all_personas() if (p.get("name") or "unnamed") == persona), None)
        persona_text = (p or {}).get("text", "")
    system = jury.assemble_system(
        d, persona_text, config.active_source_guidance(), config.active_output_contract(),
        review_rubric=config.active_review_rubric(), exemplars=config.all_exemplars(),
    )
    return {"system": system}


# ------------------------------------------------------- static SPA (prod)
if os.path.isdir(WEB_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(WEB_DIST, "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        candidate = os.path.normpath(os.path.join(WEB_DIST, path))
        if path and candidate.startswith(WEB_DIST) and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(WEB_DIST, "index.html"))
