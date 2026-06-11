/** Score → traffic-light color (same thresholds as the Streamlit app). */
export function scoreColor(score: number | null | undefined, scaleMax = 5): string {
  if (score === null || score === undefined || Number.isNaN(score)) return "#9e9e9e";
  const frac = score / scaleMax;
  if (frac >= 0.8) return "#2e7d32";
  if (frac >= 0.5) return "#f9a825";
  return "#c62828";
}

export const HARM_COLORS: Record<string, string> = {
  severe: "#c62828",
  moderate: "#f9a825",
  low: "#6c757d",
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
