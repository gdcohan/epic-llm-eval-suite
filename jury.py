"""LLM-as-jury: a panel of members scores each dimension of a candidate summary
against the source notes, and we aggregate per-dimension and overall.

- A *member* is one (provider, model, temperature, persona) judge.
- A *dimension* (see dimensions.py) is what we judge: accuracy, etc.
- Every (dimension x member) pair produces one verdict; we average them.

The jury REQUIRES a candidate summary -- the dimensions are only meaningful
relative to a summary output.
"""

import os
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone

from llm_providers import get_provider
from dimensions import DEFAULT_DIMENSIONS, OUTPUT_CONTRACT, SOURCE_GUIDANCE


@dataclass(frozen=True)
class JuryMember:
    name: str
    provider: str            # 'openai' | 'anthropic' | 'stub'
    model: str
    temperature: float = 0.2
    persona: str = ""        # optional extra system framing for diversity


DEFAULT_PERSONAS = [
    ("strict", 0.0, "Be a strict, skeptical reviewer."),
    ("balanced", 0.3, "Be a balanced, fair reviewer."),
]

_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-6",
    "openai": "gpt-4o",
    "gemini": "gemini-2.5-pro",
}


def _default_model(provider):
    return _DEFAULT_MODELS.get(provider, "")


def _parse_member_spec(spec):
    """Parse 'provider:model[:temp]' into a JuryMember.

    Examples: 'anthropic:claude-sonnet-4-6', 'openai:gpt-4o:0.2'.
    """
    parts = [p.strip() for p in spec.split(":")]
    provider = parts[0]
    model = parts[1] if len(parts) > 1 and parts[1] else _default_model(provider)
    temp = float(parts[2]) if len(parts) > 2 and parts[2] else 0.2
    return JuryMember(f"{provider}:{model}", provider, model, temp, "")


def default_panel():
    """Build the jury panel, in priority order:

    1. JURY_MODE=stub (default) -> offline deterministic panel.
    2. JURY_PANEL set -> one member per comma-separated 'provider:model[:temp]'
       spec. This is how you get TRUE cross-vendor diversity, e.g.
       JURY_PANEL="anthropic:claude-sonnet-4-6,openai:gpt-4o".
    3. Otherwise -> three personas of a single provider (JURY_PROVIDER /
       JURY_MODEL). Note: same-model personas tend to agree, so prefer a
       multi-vendor JURY_PANEL when you want meaningful disagreement.
    """
    if os.getenv("JURY_MODE", "stub").lower() == "stub":
        return [JuryMember(f"stub-{name}", "stub", "stub", temp, "") for name, temp, _ in DEFAULT_PERSONAS]

    panel_spec = os.getenv("JURY_PANEL", "").strip()
    if panel_spec:
        return [_parse_member_spec(s) for s in panel_spec.split(",") if s.strip()]

    provider = os.getenv("JURY_PROVIDER", "anthropic")
    model = os.getenv("JURY_MODEL") or _default_model(provider)
    return [
        JuryMember(f"{provider}-{name}", provider, model, temp, persona)
        for name, temp, persona in DEFAULT_PERSONAS
    ]


def _aggregate_source(notes):
    """Concatenate all source notes chronologically (oldest first) with dated
    headers, so jurors can see recency and cite which note a fact came from."""
    def date_key(n):
        return (n.get("metadata", {}) or {}).get("date") or ""

    blocks = []
    for i, note in enumerate(sorted(notes, key=date_key), start=1):
        md = note.get("metadata", {}) or {}
        header = (
            f"--- Note {i} | type={md.get('type')} | date={md.get('date')} "
            f"| id={note.get('document_reference_id')} ---"
        )
        blocks.append(f"{header}\n{note.get('combined_text', '')}")
    return "\n\n".join(blocks)


def _build_messages(dimension, source_text, candidate_summary, member, source_guidance, output_contract):
    # .replace (not .format) so a user-edited contract with literal braces is safe.
    contract = output_contract.replace("{scale}", str(dimension.scale))
    system = "\n\n".join(
        filter(None, [dimension.prompt, member.persona, source_guidance, contract])
    )
    user = (
        "=== SOURCE NOTES (ground truth, oldest first) ===\n"
        f"{source_text}\n\n"
        "=== CANDIDATE SUMMARY (to be judged) ===\n"
        f"{candidate_summary}"
    )
    return system, user


def _judge(dimension, source_text, candidate_summary, member, source_guidance, output_contract):
    system, user = _build_messages(dimension, source_text, candidate_summary, member,
                                   source_guidance, output_contract)
    try:
        result = get_provider(member.provider).complete_json(
            system, user, member.model, member.temperature
        )
        return {
            "member": member.name,
            "provider": member.provider,
            "model": member.model,
            "score": result.get("score"),
            "synopsis": result.get("synopsis") or result.get("rationale"),
            "findings": result.get("findings", []),
        }
    except Exception as exc:
        return {"member": member.name, "provider": member.provider, "error": str(exc), "score": None}


def _mean(values):
    nums = [v for v in values if isinstance(v, (int, float))]
    return round(sum(nums) / len(nums), 2) if nums else None


def _stats(scores):
    """Mean + disagreement summary for one dimension's juror scores."""
    nums = [s for s in scores if isinstance(s, (int, float))]
    if not nums:
        return {"mean": None, "min": None, "max": None, "spread": None, "stdev": None, "agreement": None}
    mean = sum(nums) / len(nums)
    spread = max(nums) - min(nums)
    stdev = (sum((x - mean) ** 2 for x in nums) / len(nums)) ** 0.5
    agreement = "unanimous" if spread == 0 else ("minor" if spread <= 1 else "split")
    return {
        "mean": round(mean, 2),
        "min": min(nums),
        "max": max(nums),
        "spread": spread,
        "stdev": round(stdev, 2),
        "agreement": agreement,
    }


def _collect_findings(verdicts):
    """Flatten jurors' findings, tagged with who raised each."""
    return [
        {**finding, "member": v.get("member")}
        for v in verdicts
        for finding in (v.get("findings") or [])
    ]


def run_jury(notes, candidate_summary, dimensions=None, panel=None, case_id=None,
             source_guidance=None, output_contract=None):
    """Score a candidate summary against the TOTALITY of its source notes.

    `notes` may be a single note dict or a list of them. Returns a verdict dict.
    """
    if isinstance(notes, dict):
        notes = [notes]
    if not candidate_summary or not str(candidate_summary).strip():
        raise ValueError("A candidate summary is required -- the jury judges it against the notes.")

    dimensions = dimensions or DEFAULT_DIMENSIONS
    panel = panel or default_panel()
    source_guidance = SOURCE_GUIDANCE if source_guidance is None else source_guidance
    output_contract = OUTPUT_CONTRACT if output_contract is None else output_contract
    source_text = _aggregate_source(notes)

    dimension_results = []
    for dim in dimensions:
        verdicts = [_judge(dim, source_text, candidate_summary, m, source_guidance, output_contract)
                    for m in panel]
        stats = _stats([v.get("score") for v in verdicts])
        dimension_results.append(
            {
                "dimension": dim.name,
                "description": dim.description,
                "scale": dim.scale,
                "mean_score": stats["mean"],
                "min_score": stats["min"],
                "max_score": stats["max"],
                "score_spread": stats["spread"],
                "score_stdev": stats["stdev"],
                "agreement": stats["agreement"],
                "findings": _collect_findings(verdicts),
                "verdicts": verdicts,
            }
        )

    spreads = [d["score_spread"] for d in dimension_results if d["score_spread"] is not None]
    return {
        "case_id": case_id,
        "source_note_ids": [n.get("document_reference_id") or n.get("input_id") for n in notes],
        "num_notes": len(notes),
        "judged_at": datetime.now(timezone.utc).isoformat(),
        "panel": [m.name for m in panel],
        "panel_members": [
            {"name": m.name, "provider": m.provider, "model": m.model, "temperature": m.temperature}
            for m in panel
        ],
        "overall_score": _mean([d["mean_score"] for d in dimension_results]),
        "max_disagreement": max(spreads) if spreads else None,
        "split_dimensions": [d["dimension"] for d in dimension_results if d.get("agreement") == "split"],
        "dimensions": dimension_results,
    }


def print_verdict(verdict):
    label = verdict.get("case_id") or ", ".join(verdict.get("source_note_ids") or [])
    print(f"\n=== Jury verdict: {label} ({verdict.get('num_notes')} note(s)) ===")
    print(f"Panel: {', '.join(verdict['panel'])}")
    for d in verdict["dimensions"]:
        n_issues = sum(1 for f in d.get("findings", []) if f.get("type") == "issue")
        print(f"  • {d['dimension']:<18} mean {d['mean_score']} / {d['scale']} "
              f"[{d.get('agreement')}, spread {d.get('score_spread')}] · {n_issues} issue(s)")
    print(f"  OVERALL: {verdict['overall_score']}")
    if verdict.get("split_dimensions"):
        print(f"  ⚠ jurors split on: {', '.join(verdict['split_dimensions'])}")
