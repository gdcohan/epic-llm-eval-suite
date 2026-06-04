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
    "The SOURCE NOTES are the full set of notes a summary was drawn from, and they "
    "may conflict with one another in several ways. Identify the conflicts and judge "
    "the CANDIDATE SUMMARY against the correctly RECONCILED clinical picture -- not "
    "against any single note in isolation.\n\n"
    "Reconcile conflicts using these principles:\n"
    "- Temporal / superseded: when a later note updates an earlier one (a value "
    "normalizes, a severity is downgraded, a diagnosis resolves, a medication "
    "changes), treat the most recent note as authoritative and earlier statements as "
    "superseded.\n"
    "- Status / certainty: prefer final over preliminary results and confirmed over "
    "suspected; never treat a 'rule-out', differential, or preliminary item as "
    "established fact.\n"
    "- Source authority: prefer the more authoritative or corrective source for its "
    "domain (e.g. a specialist consult, a signed/final note); a signed addendum "
    "overrides the text it amends.\n"
    "- Specificity: a general statement and a more specific one ('on a statin' vs "
    "'atorvastatin 40 mg') are not in conflict; prefer the specific and treat the "
    "general as consistent.\n"
    "- Repeated measures: multiple values over time describe a trend and range, not a "
    "single truth; weight the most recent reading and the overall trajectory rather "
    "than any one number.\n"
    "- Clear error: discount a statement only when it is physiologically impossible or "
    "internally contradictory -- NOT merely extreme or uncommon. Patients can have "
    "genuinely extreme values, so when in doubt treat an unusual value as real.\n\n"
    "When a conflict cannot be resolved by these principles, treat it as genuine "
    "UNCERTAINTY: a faithful summary should reflect that uncertainty (or the reconciled "
    "current picture), and should not collapse a real conflict into false certainty or "
    "silently assert one side.\n\n"
    "Apply this when scoring: do NOT penalize the summary for omitting information that "
    "was superseded, ruled out, or corrected; do NOT credit it for presenting outdated, "
    "preliminary, or contradicted information as current and confirmed; and DO penalize "
    "asserting the wrong side of a conflict or presenting an unresolved conflict as "
    "settled fact."
)

# Shared output contract appended to every dimension's system prompt.
OUTPUT_CONTRACT = (
    "Return a JSON object with exactly these keys:\n"
    '  "score": integer on the {scale} scale (higher is better),\n'
    '  "synopsis": ONE sentence summarizing your judgment,\n'
    '  "findings": an array of citation objects (may be empty), each with:\n'
    '     - "type": "issue" for a problem, or "support" for positive evidence;\n'
    '     - "summary_quote": an EXACT, character-for-character substring copied\n'
    "       from the CANDIDATE SUMMARY, or null if not applicable;\n"
    '     - "note_quote": an EXACT, character-for-character substring copied from\n'
    "       a SOURCE NOTE, or null if not applicable;\n"
    '     - "note_id": the id= of the source note that note_quote came from\n'
    "       (use the id shown in that note's header), or null;\n"
    '     - "explanation": a brief statement of what this finding shows.\n'
    "CRITICAL: quotes are matched programmatically (exact substring) to link each\n"
    "finding back to the source and highlight it in the UI. Copy them verbatim --\n"
    "do NOT paraphrase, summarize, truncate with ellipses, fix typos, or change\n"
    "wording, casing, punctuation, or whitespace. Prefer a short exact span over a\n"
    "long one. If you cannot reproduce a span exactly, set that quote to null\n"
    "rather than approximating, and rely on the explanation instead."
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
