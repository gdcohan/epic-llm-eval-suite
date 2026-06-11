"""The rubric advisor: an LLM pass that reviews each new human flag (rejected
finding + reason, harm correction, or authored missed issue) and decides
whether the REVIEWER RUBRIC needs a *generalizable* update.

Proposals are NEVER auto-applied: they queue in data/rubric_proposals.json and
surface on the Jury Config page for human accept/reject. Rejected proposals
stay visible to the advisor so it doesn't re-propose them; accepting one marks
the other pending proposals stale (they were drafted against the old rubric).

Advisory only by design: it runs in live mode, fails silent (a broken advisor
must never break the labeling flow), and is strongly biased toward NO_CHANGE.
"""

import os
import json
import uuid
from datetime import datetime, timezone

import config
from llm_providers import get_provider

PROPOSALS_PATH = os.path.join("data", "rubric_proposals.json")

INSTRUCTIONS = (
    "You maintain the REVIEWER RUBRIC for a clinical LLM-as-jury that judges "
    "GenAI summaries against source notes. The rubric is the human reviewer's "
    "house policy: what crosses the issue threshold, and how clinical harm is "
    "calibrated. You receive the current rubric, ONE new reviewer flag (a "
    "rejected jury finding with the reviewer's reason, a harm-severity "
    "correction, or a human-flagged missed issue), plus summaries of pending "
    "and previously rejected proposals.\n\n"
    "Decide whether this flag reveals a GENERALIZABLE principle that the "
    "rubric is missing, states too weakly, or contradicts.\n\n"
    "Your STRONG DEFAULT is no_change. Propose an edit only when the flag "
    "clearly generalizes beyond this single instance. Additional hard rules:\n"
    "- Do NOT add the flag as an example — a separate exemplar system handles "
    "worked examples; your only currency is general principles.\n"
    "- Prefer refining or tightening an existing clause over adding a new one.\n"
    "- Keep the rubric concise; never touch content unrelated to this flag.\n"
    "- If a pending proposal already covers this principle, return no_change.\n"
    "- Never re-propose something the reviewer previously rejected.\n\n"
    "Return a JSON object, either:\n"
    '  {"action": "no_change"}\n'
    "or:\n"
    '  {"action": "propose",\n'
    '   "change_summary": "<one line: what changes>",\n'
    '   "rationale": "<why this generalizes beyond the single flag>",\n'
    '   "revised_rubric": "<the COMPLETE revised rubric text>"}'
)


def _load():
    if os.path.exists(PROPOSALS_PATH):
        with open(PROPOSALS_PATH) as f:
            return json.load(f)
    return []


def _save(proposals):
    os.makedirs(os.path.dirname(PROPOSALS_PATH), exist_ok=True)
    with open(PROPOSALS_PATH, "w") as f:
        json.dump(proposals, f, indent=2)


def list_proposals():
    return _load()


def _advisor_member():
    """First enabled configured model judges rubric updates (temperature 0)."""
    models = [m for m in config.all_models() if m.get("enabled", True)]
    m = models[0] if models else {"provider": "anthropic", "model": "claude-sonnet-4-6"}
    return m["provider"], m.get("model", "")


def consider_example(example):
    """Run the advisor on one new human flag; returns the proposal or None.
    `example` should carry: kind ('false_alarm'|'harm_correction'|'missed_issue'),
    case_id, dimension, the quotes/explanation, and the reviewer's
    reason/note/corrections."""
    if os.getenv("JURY_MODE", "stub").lower() != "live":
        return None
    proposals = _load()
    user = json.dumps({
        "current_rubric": config.active_review_rubric(),
        "new_reviewer_flag": example,
        "pending_proposal_summaries": [
            p.get("change_summary") for p in proposals if p.get("status") == "pending"],
        "previously_rejected_proposal_summaries": [
            p.get("change_summary") for p in proposals if p.get("status") == "rejected"][-10:],
    }, indent=2)
    provider, model = _advisor_member()
    try:
        result = get_provider(provider).complete_json(INSTRUCTIONS, user, model, 0.0)
    except Exception:
        return None  # advisory only — never break the labeling flow
    if (result.get("action") or "no_change") != "propose":
        return None
    if not (result.get("revised_rubric") or "").strip():
        return None
    proposal = {
        "id": uuid.uuid4().hex[:8],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "change_summary": result.get("change_summary") or "(no summary)",
        "rationale": result.get("rationale") or "",
        "revised_rubric": result["revised_rubric"],
        "source": {k: example.get(k) for k in ("case_id", "dimension", "kind")},
    }
    proposals.append(proposal)
    _save(proposals)
    return proposal


def resolve_proposal(proposal_id, accept):
    """Accept (apply to the rubric + stale the other pendings) or reject."""
    proposals = _load()
    target = next((p for p in proposals if p.get("id") == proposal_id), None)
    if not target:
        raise ValueError(f"No rubric proposal '{proposal_id}'.")
    if target.get("status") != "pending":
        raise ValueError(f"Proposal '{proposal_id}' is already {target.get('status')}.")
    if accept:
        config.save_review_rubric(target["revised_rubric"])
        target["status"] = "accepted"
        for p in proposals:
            if p.get("status") == "pending" and p.get("id") != proposal_id:
                p["status"] = "stale"  # drafted against the now-replaced rubric
    else:
        target["status"] = "rejected"
    target["resolved_at"] = datetime.now(timezone.utc).isoformat()
    _save(proposals)
    return proposals
