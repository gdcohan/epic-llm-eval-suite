import { useState } from "react";
import type { Adjudication, DimensionResult, Finding, Verdict } from "../types";
import { fmtScore } from "../lib";
import {
  AgreementBadge,
  Badge,
  HarmBadge,
  ScoreBadge,
  buttonClass,
  inputClass,
  primaryButtonClass,
} from "./ui";

export type FocusNote = { noteId: string; quote: string } | null;

function issueFindings(d: DimensionResult): (Finding & { key?: string })[] {
  return (d.findings || []).filter((f) => f.type === "issue");
}

function FindingRow({
  finding,
  dimension,
  label,
  onFocusNote,
  onToggleLabel,
}: {
  finding: Finding & { key?: string };
  dimension: string;
  label?: "valid" | "false_alarm";
  onFocusNote: (noteId: string, quote: string) => void;
  onToggleLabel?: (finding: Finding & { key?: string }, dimension: string, label: "valid" | "false_alarm") => void;
}) {
  return (
    <div className="flex items-start gap-2 rounded-lg bg-amber-50/60 px-2.5 py-2">
      <div className="min-w-0 flex-1 text-xs text-slate-700">
        <div className="flex flex-wrap items-center gap-1.5">
          <span>⚠ {finding.explanation || "(no explanation)"}</span>
          {label === "valid" && <Badge color="#2e7d32">✓ valid</Badge>}
          {label === "false_alarm" && <Badge color="#c62828">✗ false alarm</Badge>}
          <HarmBadge finding={finding} />
        </div>
        {finding.summary_quote && (
          <div className="mt-1 text-slate-600">
            · summary: <i>“{finding.summary_quote}”</i>
          </div>
        )}
        {finding.note_quote && (
          <div className="mt-0.5 text-slate-600">
            · note <code className="rounded bg-slate-100 px-1">{finding.note_id}</code>:{" "}
            <i>“{finding.note_quote}”</i>
          </div>
        )}
        <div className="mt-0.5 text-slate-400">[{finding.member}]</div>
      </div>
      <div className="flex shrink-0 gap-1">
        {finding.note_id && finding.note_quote && (
          <button
            type="button"
            title="show source note"
            className={`${buttonClass} !px-2 !py-1 !text-xs`}
            onClick={() => onFocusNote(finding.note_id!, finding.note_quote!)}
          >
            ↪
          </button>
        )}
        {onToggleLabel && (
          <>
            <button
              type="button"
              title="valid issue"
              className={`${buttonClass} !px-2 !py-1 !text-xs ${label === "valid" ? "!border-green-500 !bg-green-50" : ""}`}
              onClick={() => onToggleLabel(finding, dimension, "valid")}
            >
              ✓
            </button>
            <button
              type="button"
              title="false alarm"
              className={`${buttonClass} !px-2 !py-1 !text-xs ${label === "false_alarm" ? "!border-red-500 !bg-red-50" : ""}`}
              onClick={() => onToggleLabel(finding, dimension, "false_alarm")}
            >
              ✗
            </button>
          </>
        )}
      </div>
    </div>
  );
}

function AdjudicateForm({
  dimension,
  juryScore,
  current,
  currentRationale,
  onSave,
}: {
  dimension: string;
  juryScore: number | null;
  current?: number;
  currentRationale?: string;
  onSave: (dimension: string, score: number | null, rationale: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [choice, setChoice] = useState<string>(current !== undefined ? String(current) : "");
  const [rationale, setRationale] = useState(currentRationale || "");
  return (
    <div className="mt-2">
      <button type="button" className="text-xs text-indigo-600 hover:underline" onClick={() => setOpen((v) => !v)}>
        ✎ adjudicate · {dimension}
      </button>
      {open && (
        <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2">
          <label className="text-xs text-slate-600">final score (jury {fmtScore(juryScore)})</label>
          <select className={`${inputClass} !w-auto !py-1`} value={choice} onChange={(e) => setChoice(e.target.value)}>
            <option value="">— (use jury)</option>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
          <input
            className={`${inputClass} !w-56 !py-1`}
            placeholder="rationale"
            value={rationale}
            onChange={(e) => setRationale(e.target.value)}
          />
          <button
            type="button"
            className={`${primaryButtonClass} !px-2.5 !py-1 !text-xs`}
            onClick={() => onSave(dimension, choice === "" ? null : Number(choice), rationale)}
          >
            Save
          </button>
        </div>
      )}
    </div>
  );
}

/** Per-dimension verdict block: scores, disagreement, juror lines, findings.
 * Adjudication controls appear only when the adjudication callbacks are given
 * (Explorer); the Live Judge renders the same view read-only. */
export default function VerdictView({
  verdict,
  adjudication,
  onFocusNote,
  onToggleLabel,
  onAdjudicate,
}: {
  verdict: Verdict;
  adjudication?: Adjudication | null;
  onFocusNote: (noteId: string, quote: string) => void;
  onToggleLabel?: (finding: Finding & { key?: string }, dimension: string, label: "valid" | "false_alarm") => void;
  onAdjudicate?: (dimension: string, score: number | null, rationale: string) => void;
}) {
  const adjDims = adjudication?.dimensions ?? {};
  const adjRationales = adjudication?.rationales ?? {};
  const findingLabels = adjudication?.finding_labels ?? {};

  return (
    <div className="space-y-4">
      {verdict.split_dimensions?.length > 0 && (
        <div className="text-xs text-amber-700">⚠ jurors split on: {verdict.split_dimensions.join(", ")}</div>
      )}
      {verdict.dimensions.map((d) => {
        const issues = issueFindings(d);
        return (
          <div key={d.dimension} className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-slate-800">{d.dimension}</span>
              <ScoreBadge score={d.mean_score} scale={d.scale} />
              <AgreementBadge agreement={d.agreement} />
              <span className="text-xs text-slate-400">(spread {fmtScore(d.score_spread)})</span>
            </div>
            {d.dimension in adjDims && (
              <div className="mt-1 flex items-center gap-2">
                <Badge color="#1565c0">✎ adjudicated {adjDims[d.dimension]}</Badge>
                <span className="text-xs text-slate-500">(jury {fmtScore(d.mean_score)})</span>
                {adjRationales[d.dimension] && (
                  <span className="text-xs text-slate-500">✎ {adjRationales[d.dimension]}</span>
                )}
              </div>
            )}
            <ul className="mt-2 space-y-1">
              {d.verdicts.map((v, i) => (
                <li key={i} className="text-xs text-slate-600">
                  {v.error ? (
                    <>
                      <b>{v.member}</b>: ⚠️ {v.error}
                    </>
                  ) : (
                    <>
                      <b>{v.member}</b> ({fmtScore(v.score)}): {v.synopsis || ""}
                    </>
                  )}
                </li>
              ))}
            </ul>
            {issues.length > 0 && (
              <div className="mt-2 space-y-1.5">
                {onToggleLabel && (
                  <div className="text-xs font-medium text-slate-500">
                    issues — mark each ✓ valid / ✗ false alarm
                  </div>
                )}
                {issues.map((f, i) => (
                  <FindingRow
                    key={f.key ?? i}
                    finding={f}
                    dimension={d.dimension}
                    label={f.key ? findingLabels[f.key]?.label : undefined}
                    onFocusNote={onFocusNote}
                    onToggleLabel={onToggleLabel}
                  />
                ))}
              </div>
            )}
            {onAdjudicate && (
              <AdjudicateForm
                key={`${d.dimension}-${adjDims[d.dimension] ?? "jury"}`}
                dimension={d.dimension}
                juryScore={d.mean_score}
                current={adjDims[d.dimension]}
                currentRationale={adjRationales[d.dimension]}
                onSave={onAdjudicate}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
