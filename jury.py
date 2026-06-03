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


def default_panel():
    """Build the default jury from env.

    JURY_MODE=stub (default) -> offline deterministic panel.
    JURY_MODE=live           -> diversity via one provider (JURY_PROVIDER,
                                JURY_MODEL); add cross-vendor members trivially.
    """
    mode = os.getenv("JURY_MODE", "stub").lower()
    if mode == "stub":
        return [JuryMember(f"stub-{t}", "stub", "stub", t) for t in (0.0, 0.3, 0.6)]

    provider = os.getenv("JURY_PROVIDER", "anthropic")
    model = os.getenv("JURY_MODEL", "claude-sonnet-4-6")
    # Diversity through one provider: vary temperature + persona. To span vendors,
    # append e.g. JuryMember("gpt", "openai", "gpt-4o", 0.2) here.
    return [
        JuryMember(f"{provider}-strict", provider, model, 0.0, "Be a strict, skeptical reviewer."),
        JuryMember(f"{provider}-balanced", provider, model, 0.3, "Be a balanced, fair reviewer."),
        JuryMember(f"{provider}-lenient", provider, model, 0.6, "Be a charitable reviewer who rewards intent."),
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


def _build_messages(dimension, source_text, candidate_summary, member):
    system = "\n\n".join(
        filter(
            None,
            [
                member.persona,
                dimension.prompt,
                SOURCE_GUIDANCE,
                OUTPUT_CONTRACT.format(scale=dimension.scale),
            ],
        )
    )
    user = (
        "=== SOURCE NOTES (ground truth, oldest first) ===\n"
        f"{source_text}\n\n"
        "=== CANDIDATE SUMMARY (to be judged) ===\n"
        f"{candidate_summary}"
    )
    return system, user


def _judge(dimension, source_text, candidate_summary, member):
    system, user = _build_messages(dimension, source_text, candidate_summary, member)
    try:
        result = get_provider(member.provider).complete_json(
            system, user, member.model, member.temperature
        )
        return {
            "member": member.name,
            "provider": member.provider,
            "model": member.model,
            "score": result.get("score"),
            "rationale": result.get("rationale"),
            "supporting_evidence": result.get("supporting_evidence", []),
            "issues": result.get("issues", []),
        }
    except Exception as exc:
        return {"member": member.name, "provider": member.provider, "error": str(exc), "score": None}


def _mean(values):
    nums = [v for v in values if isinstance(v, (int, float))]
    return round(sum(nums) / len(nums), 2) if nums else None


def run_jury(notes, candidate_summary, dimensions=None, panel=None, case_id=None):
    """Score a candidate summary against the TOTALITY of its source notes.

    `notes` may be a single note dict or a list of them. Returns a verdict dict.
    """
    if isinstance(notes, dict):
        notes = [notes]
    if not candidate_summary or not str(candidate_summary).strip():
        raise ValueError("A candidate summary is required -- the jury judges it against the notes.")

    dimensions = dimensions or DEFAULT_DIMENSIONS
    panel = panel or default_panel()
    source_text = _aggregate_source(notes)

    dimension_results = []
    for dim in dimensions:
        verdicts = [_judge(dim, source_text, candidate_summary, m) for m in panel]
        dimension_results.append(
            {
                "dimension": dim.name,
                "description": dim.description,
                "scale": dim.scale,
                "mean_score": _mean([v.get("score") for v in verdicts]),
                "verdicts": verdicts,
            }
        )

    return {
        "case_id": case_id,
        "source_note_ids": [n.get("document_reference_id") or n.get("input_id") for n in notes],
        "num_notes": len(notes),
        "judged_at": datetime.now(timezone.utc).isoformat(),
        "panel": [m.name for m in panel],
        "overall_score": _mean([d["mean_score"] for d in dimension_results]),
        "dimensions": dimension_results,
    }


def print_verdict(verdict):
    label = verdict.get("case_id") or ", ".join(verdict.get("source_note_ids") or [])
    print(f"\n=== Jury verdict: {label} ({verdict.get('num_notes')} note(s)) ===")
    print(f"Panel: {', '.join(verdict['panel'])}")
    for d in verdict["dimensions"]:
        print(f"  • {d['dimension']:<18} mean {d['mean_score']} / {d['scale']}")
    print(f"  OVERALL: {verdict['overall_score']}")
