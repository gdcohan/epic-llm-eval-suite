export interface PanelInfo {
  mode: string;
  members: string[];
  panel: string[];
  n_dimensions: number;
  calls_per_case: number;
}

export interface CaseMeta {
  case_id: string;
  path: string;
  summary_preview: string;
  source: string | null;
  source_note_ids: string[];
  overall: number | null;
  judged: boolean;
}

export interface CaseManifest {
  case_id: string;
  created_at?: string;
  summary: { text?: string; path?: string; source?: string; generated_at?: string };
  source_note_ids: string[];
}

export interface NoteData {
  document_reference_id: string;
  input_id?: string;
  resolved_via?: string;
  combined_text?: string;
  metadata: { type?: string | null; date?: string | null; [k: string]: unknown };
  raw_document_reference?: unknown;
}

export interface Finding {
  type: string;
  summary_quote?: string | null;
  note_quote?: string | null;
  note_id?: string | null;
  explanation?: string;
  member?: string;
  harm_category?: string | null;
  harm_severity?: string | null;
}

export interface JurorVerdict {
  member?: string;
  provider?: string;
  model?: string;
  score?: number | null;
  synopsis?: string | null;
  error?: string;
}

export interface DimensionResult {
  dimension: string;
  description?: string;
  scale: string;
  mean_score: number | null;
  min_score: number | null;
  max_score: number | null;
  score_spread: number | null;
  score_stdev: number | null;
  agreement: string | null;
  findings: Finding[];
  verdicts: JurorVerdict[];
}

export interface Verdict {
  case_id: string | null;
  source_note_ids: (string | null)[];
  num_notes: number;
  judged_at: string;
  panel: string[];
  overall_score: number | null;
  max_disagreement: number | null;
  split_dimensions: string[];
  dimensions: DimensionResult[];
}

export interface FindingLabel {
  label: "valid" | "false_alarm";
  dimension?: string;
  member?: string | null;
  summary_quote?: string | null;
  note_quote?: string | null;
  note_id?: string | null;
  reason?: string;
  note?: string;
  corrected_harm_category?: string;
  corrected_harm_severity?: string;
}

export interface Exemplar {
  id: string;
  dimension: string;
  kind: "valid" | "false_alarm" | "missed";
  summary_quote?: string | null;
  note_quote?: string | null;
  explanation?: string | null;
  reason?: string | null;
  teaching_note?: string | null;
  harm_category?: string | null;
  harm_severity?: string | null;
}

export interface RubricProposal {
  id: string;
  created_at: string;
  status: "pending" | "accepted" | "rejected" | "stale";
  change_summary: string;
  rationale: string;
  revised_rubric: string;
  source?: { case_id?: string; dimension?: string; kind?: string };
}

export interface AuthoredFinding {
  id: string;
  dimension: string;
  explanation: string;
  note_quote?: string | null;
  note_id?: string | null;
  harm_category?: string | null;
  harm_severity?: string | null;
  author?: string;
  created_at?: string;
}

export interface Adjudication {
  case_id: string;
  dimensions: Record<string, number>;
  rationales: Record<string, string>;
  finding_labels?: Record<string, FindingLabel>;
  authored_findings?: AuthoredFinding[];
  adjudicator?: string;
  adjudicated_at?: string;
}

export interface CaseDetail {
  case: CaseManifest;
  notes: NoteData[];
  missing_note_ids: string[];
  verdict: Verdict | null;
  adjudication: Adjudication | null;
}

export interface OverviewRow {
  case: string;
  overall: number | null;
  issues: number | null;
  agreement: string;
  judged: boolean;
  max_harm?: string;
  adjudicated?: string;
  [dimension: string]: unknown;
}

export interface OverviewStats {
  rows: OverviewRow[];
  dims: string[];
  kpis: {
    cases: number;
    judged: number;
    avg_overall: number | null;
    with_issues: number;
    severe_cases: number;
    splits: number;
  };
  avg_by_dim: Record<string, number>;
  issues_by_dim: Record<string, number>;
  harm_matrix: Record<string, Record<string, number>>;
  harm_matrix_cases: Record<string, Record<string, string[]>>;
  harm_categories: string[];
}

export interface PrecisionStats {
  per_dimension: Record<
    string,
    {
      labeled: number;
      validated: number;
      false_alarms: number;
      precision: number | null;
      authored_missed: number;
    }
  >;
  labeled_cases: number;
  total_labeled: number;
  overall_precision: number | null;
  total_authored: number;
  false_alarms: Array<{
    case: string;
    dimension?: string;
    summary_quote?: string | null;
    note_quote?: string | null;
  }>;
}

export interface DimensionConfig {
  name: string;
  description: string;
  prompt: string;
  scale: string;
  enabled: boolean;
}

export interface PersonaConfig {
  name: string;
  temperature: number;
  text: string;
  enabled: boolean;
}

export interface ModelConfig {
  provider: string;
  model: string;
  enabled: boolean;
}

export interface JuryConfigData {
  dimensions: DimensionConfig[];
  personas: PersonaConfig[];
  models: ModelConfig[];
  source_guidance: string;
  output_contract: string;
  review_rubric: string;
  exemplars: Exemplar[];
  exemplar_cap: number;
}
