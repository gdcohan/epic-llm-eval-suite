"""Jury dimensions: each is a jurist with its own prompt.

A dimension judges the CANDIDATE SUMMARY *relative to* the SOURCE NOTES -- the
verdict is only meaningful with the summary present. Add a dimension by appending
one Dimension to DEFAULT_DIMENSIONS (or build your own list and pass it in).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Dimension:
    name: str
    description: str
    prompt: str
    scale: str = "1-5"


# Shared output contract appended to every dimension's system prompt.
OUTPUT_CONTRACT = (
    "Return a JSON object with exactly these keys:\n"
    '  "score": integer on the {scale} scale (higher is better),\n'
    '  "rationale": a concise justification for the score,\n'
    '  "supporting_evidence": array of short quotes/spans from the SOURCE NOTES,\n'
    '  "issues": array of specific problems you found (empty if none).'
)


DEFAULT_DIMENSIONS = [
    Dimension(
        name="accuracy",
        description="Every claim in the summary is supported by the source notes.",
        prompt=(
            "You are a clinical documentation reviewer judging ACCURACY. Determine "
            "whether every clinical claim in the CANDIDATE SUMMARY is directly "
            "supported by the SOURCE NOTES. Penalize fabrications, hallucinations, "
            "and unsupported inferences. A perfect score means no claim lacks "
            "support in the source notes."
        ),
    ),
    Dimension(
        name="comprehensiveness",
        description="The summary captures all clinically significant information.",
        prompt=(
            "You are a clinical documentation reviewer judging COMPREHENSIVENESS. "
            "Determine whether the CANDIDATE SUMMARY captures all clinically "
            "significant information from the SOURCE NOTES. Penalize omissions of "
            "important diagnoses, medications, results, plans, or safety-relevant "
            "details. A perfect score means nothing clinically important was dropped."
        ),
    ),
    Dimension(
        name="correctness",
        description="The summary is free of factual/medical errors vs. the source.",
        prompt=(
            "You are a clinical documentation reviewer judging CORRECTNESS. "
            "Determine whether the CANDIDATE SUMMARY is free of factual or medical "
            "errors relative to the SOURCE NOTES -- wrong values, swapped entities, "
            "misstated dosages, reversed conclusions, or temporal mistakes. A "
            "perfect score means there are no misstatements relative to the source."
        ),
    ),
]
