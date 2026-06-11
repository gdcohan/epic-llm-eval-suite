import { useState } from "react";
import type { Adjudication, DimensionResult, Finding, Verdict } from "../types";
import { fmtScore, scoreColor } from "../lib";
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

type LabeledFinding = Finding & { key?: string };
type ToggleLabel = (finding: LabeledFinding, dimension: string, label: "valid" | "false_alarm") => void;

function issueFindings(d: DimensionResult): LabeledFinding[] {
  return (d.findings || []).filter((f) => f.type === "issue");
}

function FindingRow({
  finding,
  dimension,
  label,
  onFocusNote,
  onToggleLabel,
}: {
  finding: LabeledFinding;
  dimension: string;
  label?: "valid" | "false_alarm";
  onFocusNote: (noteId: string, quote: string) => void;
  onToggleLabel?: ToggleLabel;
}) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-white px-2.5 py-2">
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
    <div>
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

/** One collapsible dimension card: a scannable header (score, agreement,
 * issue count) over two distinct zones — the jury verdict (juror scores +
 * synopses) and the amber flagged-issues list. */
function DimensionCard({
  d,
  adjudication,
  onFocusNote,
  onToggleLabel,
  onAdjudicate,
}: {
  d: DimensionResult;
  adjudication?: Adjudication | null;
  onFocusNote: (noteId: string, quote: string) => void;
  onToggleLabel?: ToggleLabel;
  onAdjudicate?: (dimension: string, score: number | null, rationale: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const [issuesOpen, setIssuesOpen] = useState(false);
  const issues = issueFindings(d);
  const adjDims = adjudication?.dimensions ?? {};
  const adjRationales = adjudication?.rationales ?? {};
  const findingLabels = adjudication?.finding_labels ?? {};
  const adjudicated = d.dimension in adjDims;

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full flex-wrap items-center gap-2 px-3 py-2.5 text-left hover:bg-slate-50"
      >
        <span className="text-slate-400">{open ? "▾" : "▸"}</span>
        <span className="font-semibold text-slate-800">{d.dimension}</span>
        <ScoreBadge score={d.mean_score} scale={d.scale} />
        <AgreementBadge agreement={d.agreement} />
        {adjudicated && <Badge color="#1565c0">✎ {adjDims[d.dimension]}</Badge>}
        <span className="min-w-2 flex-1" />
        {issues.length > 0 ? (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
            ⚠ {issues.length} issue{issues.length === 1 ? "" : "s"}
          </span>
        ) : (
          <span className="text-xs text-slate-400">no issues</span>
        )}
      </button>

      {open && (
        <div className="border-t border-slate-100">
          {/* zone 1: the jury's verdict */}
          <div className="px-4 py-3">
            <div className="mb-2.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              Jury verdict <span className="font-normal normal-case">· spread {fmtScore(d.score_spread)}</span>
            </div>
            {adjudicated && (
              <div className="mb-2.5 flex flex-wrap items-center gap-2 text-sm text-slate-500">
                <Badge color="#1565c0">✎ adjudicated {adjDims[d.dimension]}</Badge>
                <span>(jury {fmtScore(d.mean_score)})</span>
                {adjRationales[d.dimension] && <span>✎ {adjRationales[d.dimension]}</span>}
              </div>
            )}
            <ul className="space-y-2.5">
              {d.verdicts.map((v, i) => (
                <li key={i} className="flex items-start gap-2.5">
                  <span
                    className="mt-0.5 inline-block w-9 shrink-0 rounded px-1 py-0.5 text-center text-xs font-semibold text-white"
                    style={{ background: v.error ? "#9e9e9e" : scoreColor(v.score ?? null) }}
                  >
                    {v.error ? "—" : fmtScore(v.score)}
                  </span>
                  <div className="min-w-0 text-[13px] leading-relaxed">
                    <div className="font-medium text-slate-700">{v.member}</div>
                    {v.error ? (
                      <div className="text-red-700">⚠️ {v.error}</div>
                    ) : (
                      <div className="text-slate-600">{v.synopsis || ""}</div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {/* zone 2: flagged issues, visually set apart + collapsible on their own */}
          {issues.length > 0 && (
            <div className="border-t border-amber-200 bg-amber-50/60">
              <button
                type="button"
                onClick={() => setIssuesOpen((v) => !v)}
                className="flex w-full items-center gap-1.5 px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-amber-700 hover:bg-amber-100/60"
              >
                <span>{issuesOpen ? "▾" : "▸"}</span>
                <span>⚠ Flagged issues ({issues.length})</span>
                {onToggleLabel && issuesOpen && (
                  <span className="font-normal normal-case">— mark each ✓ valid / ✗ false alarm</span>
                )}
              </button>
              {issuesOpen && (
                <div className="space-y-2 px-4 pb-3">
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
            </div>
          )}

          {/* zone 3: human adjudication */}
          {onAdjudicate && (
            <div className="border-t border-slate-100 px-3 py-2">
              <AdjudicateForm
                key={`${d.dimension}-${adjDims[d.dimension] ?? "jury"}`}
                dimension={d.dimension}
                juryScore={d.mean_score}
                current={adjDims[d.dimension]}
                currentRationale={adjRationales[d.dimension]}
                onSave={onAdjudicate}
              />
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** Per-dimension verdict blocks. Adjudication controls appear only when the
 * adjudication callbacks are given (Explorer); the Live Judge renders the
 * same view read-only. */
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
  onToggleLabel?: ToggleLabel;
  onAdjudicate?: (dimension: string, score: number | null, rationale: string) => void;
}) {
  return (
    <div className="space-y-3">
      {verdict.split_dimensions?.length > 0 && (
        <div className="text-xs text-amber-700">⚠ jurors split on: {verdict.split_dimensions.join(", ")}</div>
      )}
      {verdict.dimensions.map((d) => (
        <DimensionCard
          key={d.dimension}
          d={d}
          adjudication={adjudication}
          onFocusNote={onFocusNote}
          onToggleLabel={onToggleLabel}
          onAdjudicate={onAdjudicate}
        />
      ))}
    </div>
  );
}
