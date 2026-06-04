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


# Shared guidance prepended to every dimension's system prompt: how to treat a
# set of notes that span time and may disagree.
SOURCE_GUIDANCE = (
    "The SOURCE NOTES are the totality of notes a summary was drawn from. They "
    "may span multiple dates and may disagree with one another. When notes "
    "conflict, treat the MORE RECENT note as authoritative and consider older "
    "statements superseded -- unless the more recent note is clearly erroneous. "
    "Judge the summary against this reconciled, most-current clinical picture: do "
    "not penalize the summary for omitting details that a later note superseded, "
    "and do not credit it for presenting outdated information as if it were current."
)

# Shared output contract appended to every dimension's system prompt.
OUTPUT_CONTRACT = (
    "Return a JSON object with exactly these keys:\n"
    '  "score": integer on the {scale} scale (higher is better),\n'
    '  "rationale": a concise justification for the score,\n'
    '  "supporting_evidence": array of short quotes/spans your judgment rests on'
    " (from the notes and/or the summary, whichever is relevant to this dimension),\n"
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
        description="The summary is medically sound and internally consistent on its own terms.",
        prompt=(
            "You are a clinical reviewer judging CORRECTNESS -- the intrinsic "
            "medical validity and internal coherence of the CANDIDATE SUMMARY, "
            "using your own clinical knowledge. Judge each statement on its own "
            "merits, INDEPENDENTLY of the SOURCE NOTES. Two consequences of this: "
            "(a) a statement can be faithfully copied from the notes and still be "
            "incorrect, so do NOT treat presence in the notes as evidence of "
            "correctness; and (b) do NOT penalize a statement merely for "
            "disagreeing with, being unsupported by, or being absent from the "
            "notes, nor for citing a fabricated value, SO LONG AS the value is "
            "medically plausible -- factual fidelity to the notes is the accuracy "
            "reviewer's job, not yours. A medically plausible, internally "
            "consistent claim is CORRECT here even if it happens to be factually "
            "wrong about this patient. Flag only what is medically nonsensical or "
            "implausible on its face: a drug paired with the wrong indication "
            "(e.g. a statin 'for diabetes', or 'nifedipine to lower blood sugar'), "
            "doses outside sane ranges, physiologically impossible or "
            "self-contradictory values, and reasoning that does not follow. A "
            "perfect score means the summary is medically sound and internally "
            "consistent as written."
        ),
    ),
]
