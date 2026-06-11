// Muted clinical palette (deliberately not stoplight-saturated).
export const COLORS = {
  good: "#4a7c6f", // viridian
  mid: "#c0913d", // ochre
  bad: "#b0564c", // terracotta
  info: "#4a6fa5", // steel blue — human actions (adjudications, flags)
  muted: "#8b95a3", // gray — null / low
};

/** Score → traffic-light color (same thresholds as the Streamlit app). */
export function scoreColor(score: number | null | undefined, scaleMax = 5): string {
  if (score === null || score === undefined || Number.isNaN(score)) return COLORS.muted;
  const frac = score / scaleMax;
  if (frac >= 0.8) return COLORS.good;
  if (frac >= 0.5) return COLORS.mid;
  return COLORS.bad;
}

export const HARM_COLORS: Record<string, string> = {
  severe: COLORS.bad,
  moderate: COLORS.mid,
  low: COLORS.muted,
};

// mirrors service.HARM_CATEGORIES
export const HARM_CATEGORIES = [
  "medication/dosing",
  "allergy",
  "diagnosis",
  "test/result",
  "follow-up/plan",
  "demographic/admin",
  "other",
];

// rejection-reason taxonomy for ✗ false-alarm labels (mirrored in the rubric
// advisor's context — keep wording stable)
export const REJECTION_REASONS = [
  "phrasing/style",
  "clinically equivalent",
  "defensible judgment call",
  "true but trivial",
  "misread the note",
  "other",
];

export const AGREEMENT_LABELS: Record<string, string> = {
  unanimous: "✅ unanimous",
  minor: "🟡 minor split",
  split: "🔴 split",
};

/** Split free-text IDs on whitespace / commas. */
export function splitIds(raw: string): string[] {
  return raw.split(/[\s,]+/).filter((t) => t.trim());
}

/** Split pasted note text into notes on lines containing only `---`. */
export function splitPasted(raw: string): string[] {
  return raw.split(/^[ \t]*---[ \t]*$/m).map((c) => c.trim()).filter(Boolean);
}

export function fmtScore(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return Number.isInteger(v) ? String(v) : v.toFixed(2);
}
