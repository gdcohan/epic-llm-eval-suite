import { useState } from "react";
import type {
  Adjudication,
  AuthoredFinding,
  DimensionResult,
  Finding,
  FindingLabel,
  Verdict,
} from "../types";
import { HARM_CATEGORIES, REJECTION_REASONS, fmtScore, scoreColor } from "../lib";
import {
  AgreementBadge,
  Badge,
  HarmBadge,
  ScoreBadge,
  buttonClass,
  inputClass,
  primaryButtonClass,
  textareaClass,
} from "./ui";

export type FocusNote = { noteId: string; quote: string } | null;

export type AuthoredDraft = {
  explanation: string;
  note_quote: string;
  note_id: string;
  harm_category: string;
  harm_severity: string;
};

export type LabelPayload = {
  label: "valid" | "false_alarm" | null;
  reason?: string;
  note?: string;
  corrected_harm_category?: string;
  corrected_harm_severity?: string;
};

export type ExemplarDraft = {
  dimension: string;
  kind: "valid" | "false_alarm" | "missed";
  summary_quote?: string | null;
  note_quote?: string | null;
  explanation?: string | null;
  reason?: string | null;
  teaching_note?: string | null;
  harm_category?: string | null;
  harm_severity?: string | null;
};

type LabeledFinding = Finding & { key?: string };
type OnLabel = (finding: LabeledFinding, dimension: string, payload: LabelPayload) => void;
type OnPromote = (draft: ExemplarDraft) => void;
type AuthorFinding = (dimension: string, draft: AuthoredDraft) => void;

function HarmSelects({
  category,
  severity,
  setCategory,
  setSeverity,
}: {
  category: string;
  severity: string;
  setCategory: (v: string) => void;
  setSeverity: (v: string) => void;
}) {
  return (
    <>
      <select className={`${inputClass} !w-auto !py-1 !text-xs`} value={category} onChange={(e) => setCategory(e.target.value)}>
        <option value="">harm category…</option>
        {HARM_CATEGORIES.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>
      <select className={`${inputClass} !w-auto !py-1 !text-xs`} value={severity} onChange={(e) => setSeverity(e.target.value)}>
        <option value="">severity…</option>
        {["low", "moderate", "severe"].map((s) => (
          <option key={s} value={s}>
            {s}
          </option>
        ))}
      </select>
    </>
  );
}

function issueFindings(d: DimensionResult): LabeledFinding[] {
  return (d.findings || []).filter((f) => f.type === "issue");
}

function FindingRow({
  finding,
  dimension,
  labelEntry,
  onFocusNote,
  onLabel,
  onPromote,
}: {
  finding: LabeledFinding;
  dimension: string;
  labelEntry?: FindingLabel;
  onFocusNote: (noteId: string, quote: string) => void;
  onLabel?: OnLabel;
  onPromote?: OnPromote;
}) {
  const label = labelEntry?.label;
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const [teachNote, setTeachNote] = useState("");
  const [editingHarm, setEditingHarm] = useState(false);
  const [harmCat, setHarmCat] = useState(labelEntry?.corrected_harm_category ?? "");
  const [harmSev, setHarmSev] = useState(labelEntry?.corrected_harm_severity ?? "");

  const correctedHarm = labelEntry?.corrected_harm_severity || labelEntry?.corrected_harm_category;

  return (
    <div className="rounded-lg border border-amber-200 bg-white px-2.5 py-2">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1 text-xs text-slate-700">
          <div className="flex flex-wrap items-center gap-1.5">
            <span>⚠ {finding.explanation || "(no explanation)"}</span>
            {label === "valid" && <Badge color="#2e7d32">✓ valid</Badge>}
            {label === "false_alarm" && (
              <>
                <Badge color="#c62828">✗ false alarm</Badge>
                {labelEntry?.reason && <Badge color="#6c757d">{labelEntry.reason}</Badge>}
              </>
            )}
            <HarmBadge finding={finding} />
            {correctedHarm && (
              <Badge color="#1565c0">
                ✎ harm: {labelEntry?.corrected_harm_severity || "—"}
                {labelEntry?.corrected_harm_category ? ` · ${labelEntry.corrected_harm_category}` : ""}
              </Badge>
            )}
          </div>
          {labelEntry?.note && <div className="mt-1 italic text-slate-500">✎ {labelEntry.note}</div>}
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
          {onLabel && (
            <>
              <button
                type="button"
                title="valid issue"
                className={`${buttonClass} !px-2 !py-1 !text-xs ${label === "valid" ? "!border-green-500 !bg-green-50" : ""}`}
                onClick={() => {
                  setRejecting(false);
                  onLabel(finding, dimension, { label: label === "valid" ? null : "valid" });
                }}
              >
                ✓
              </button>
              <button
                type="button"
                title="false alarm (asks why)"
                className={`${buttonClass} !px-2 !py-1 !text-xs ${label === "false_alarm" ? "!border-red-500 !bg-red-50" : ""}`}
                onClick={() => {
                  if (label === "false_alarm") onLabel(finding, dimension, { label: null });
                  else setRejecting((v) => !v);
                }}
              >
                ✗
              </button>
              {label === "valid" && (
                <button
                  type="button"
                  title="correct the harm rating"
                  className={`${buttonClass} !px-2 !py-1 !text-xs ${correctedHarm ? "!border-blue-400 !bg-blue-50" : ""}`}
                  onClick={() => setEditingHarm((v) => !v)}
                >
                  ✎
                </button>
              )}
              {label && onPromote && (
                <button
                  type="button"
                  title="promote to exemplar (teaches the jury via the prompt)"
                  className={`${buttonClass} !px-2 !py-1 !text-xs`}
                  onClick={() =>
                    onPromote({
                      dimension,
                      kind: label === "valid" ? "valid" : "false_alarm",
                      summary_quote: finding.summary_quote,
                      note_quote: finding.note_quote,
                      explanation: finding.explanation,
                      reason: labelEntry?.reason,
                      teaching_note: labelEntry?.note,
                      harm_category: labelEntry?.corrected_harm_category ?? finding.harm_category,
                      harm_severity: labelEntry?.corrected_harm_severity ?? finding.harm_severity,
                    })
                  }
                >
                  ★
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {rejecting && onLabel && (
        <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2">
          <select className={`${inputClass} !w-auto !py-1 !text-xs`} value={reason} onChange={(e) => setReason(e.target.value)}>
            <option value="">why is this a false alarm…</option>
            {REJECTION_REASONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <input
            className={`${inputClass} !w-64 !py-1 !text-xs`}
            placeholder="teach the jury (optional)"
            value={teachNote}
            onChange={(e) => setTeachNote(e.target.value)}
          />
          <button
            type="button"
            className={`${primaryButtonClass} !px-2.5 !py-1 !text-xs`}
            disabled={!reason}
            onClick={() => {
              onLabel(finding, dimension, { label: "false_alarm", reason, note: teachNote });
              setRejecting(false);
            }}
          >
            Save ✗
          </button>
          <button type="button" className={`${buttonClass} !px-2 !py-1 !text-xs`} onClick={() => setRejecting(false)}>
            cancel
          </button>
        </div>
      )}

      {editingHarm && onLabel && label === "valid" && (
        <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 p-2">
          <span className="text-xs text-slate-600">
            corrected harm (jury said {finding.harm_severity || "—"}
            {finding.harm_category ? ` · ${finding.harm_category}` : ""})
          </span>
          <HarmSelects category={harmCat} severity={harmSev} setCategory={setHarmCat} setSeverity={setHarmSev} />
          <button
            type="button"
            className={`${primaryButtonClass} !px-2.5 !py-1 !text-xs`}
            onClick={() => {
              onLabel(finding, dimension, {
                label: "valid",
                corrected_harm_category: harmCat,
                corrected_harm_severity: harmSev,
              });
              setEditingHarm(false);
            }}
          >
            Save
          </button>
          <button type="button" className={`${buttonClass} !px-2 !py-1 !text-xs`} onClick={() => setEditingHarm(false)}>
            cancel
          </button>
        </div>
      )}
    </div>
  );
}

/** A human-flagged missed issue (e.g. an omission the jury didn't catch). */
function AuthoredRow({
  finding,
  onFocusNote,
  onRemove,
  onPromote,
}: {
  finding: AuthoredFinding;
  onFocusNote: (noteId: string, quote: string) => void;
  onRemove?: (id: string) => void;
  onPromote?: OnPromote;
}) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-blue-200 bg-white px-2.5 py-2">
      <div className="min-w-0 flex-1 text-xs text-slate-700">
        <div className="flex flex-wrap items-center gap-1.5">
          <span>✋ {finding.explanation || "(no explanation)"}</span>
          <Badge color="#1565c0">human-flagged</Badge>
          <HarmBadge finding={finding} />
        </div>
        {finding.note_quote && (
          <div className="mt-1 text-slate-600">
            · note <code className="rounded bg-slate-100 px-1">{finding.note_id || "—"}</code>:{" "}
            <i>“{finding.note_quote}”</i>
          </div>
        )}
        <div className="mt-0.5 text-slate-400">[{finding.author || "human"}]</div>
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
        {onPromote && (
          <button
            type="button"
            title="promote to exemplar (teaches the jury via the prompt)"
            className={`${buttonClass} !px-2 !py-1 !text-xs`}
            onClick={() =>
              onPromote({
                dimension: finding.dimension,
                kind: "missed",
                note_quote: finding.note_quote,
                explanation: finding.explanation,
                harm_category: finding.harm_category,
                harm_severity: finding.harm_severity,
              })
            }
          >
            ★
          </button>
        )}
        {onRemove && (
          <button
            type="button"
            title="remove this flag"
            className={`${buttonClass} !px-2 !py-1 !text-xs text-red-600`}
            onClick={() => onRemove(finding.id)}
          >
            ×
          </button>
        )}
      </div>
    </div>
  );
}

const EMPTY_DRAFT: AuthoredDraft = {
  explanation: "",
  note_quote: "",
  note_id: "",
  harm_category: "",
  harm_severity: "",
};

function AuthorFindingForm({
  dimension,
  onSave,
}: {
  dimension: string;
  onSave: AuthorFinding;
}) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<AuthoredDraft>(EMPTY_DRAFT);
  const set = (patch: Partial<AuthoredDraft>) => setDraft((d) => ({ ...d, ...patch }));
  return (
    <div>
      <button type="button" className="text-xs text-indigo-600 hover:underline" onClick={() => setOpen((v) => !v)}>
        ✋ flag missed issue · {dimension}
      </button>
      {open && (
        <div className="mt-2 space-y-2 rounded-lg border border-slate-200 bg-slate-50 p-2">
          <input
            className={inputClass}
            placeholder="what did the jury miss? (e.g. summary omits the penicillin allergy)"
            value={draft.explanation}
            onChange={(e) => set({ explanation: e.target.value })}
          />
          <textarea
            className={textareaClass}
            rows={2}
            placeholder="the omitted info, copied verbatim from the note (enables the ↪ source link)"
            value={draft.note_quote}
            onChange={(e) => set({ note_quote: e.target.value })}
          />
          <div className="flex flex-wrap items-center gap-2">
            <input
              className={`${inputClass} !w-44 !py-1`}
              placeholder="note id (optional)"
              value={draft.note_id}
              onChange={(e) => set({ note_id: e.target.value })}
            />
            <select
              className={`${inputClass} !w-auto !py-1`}
              value={draft.harm_category}
              onChange={(e) => set({ harm_category: e.target.value })}
            >
              <option value="">harm category…</option>
              {HARM_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <select
              className={`${inputClass} !w-auto !py-1`}
              value={draft.harm_severity}
              onChange={(e) => set({ harm_severity: e.target.value })}
            >
              <option value="">severity…</option>
              {["low", "moderate", "severe"].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
            <button
              type="button"
              className={`${primaryButtonClass} !px-2.5 !py-1 !text-xs`}
              disabled={!draft.explanation.trim() && !draft.note_quote.trim()}
              onClick={() => {
                onSave(dimension, draft);
                setDraft(EMPTY_DRAFT);
                setOpen(false);
              }}
            >
              Save flag
            </button>
          </div>
        </div>
      )}
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
  onLabel,
  onAdjudicate,
  onAuthorFinding,
  onRemoveAuthored,
  onPromote,
}: {
  d: DimensionResult;
  adjudication?: Adjudication | null;
  onFocusNote: (noteId: string, quote: string) => void;
  onLabel?: OnLabel;
  onAdjudicate?: (dimension: string, score: number | null, rationale: string) => void;
  onAuthorFinding?: AuthorFinding;
  onRemoveAuthored?: (id: string) => void;
  onPromote?: OnPromote;
}) {
  const [open, setOpen] = useState(true);
  const [issuesOpen, setIssuesOpen] = useState(false);
  const issues = issueFindings(d);
  const authored = (adjudication?.authored_findings ?? []).filter((f) => f.dimension === d.dimension);
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
        {authored.length > 0 && (
          <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800">
            ✋ {authored.length} human
          </span>
        )}
        {issues.length > 0 ? (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
            ⚠ {issues.length} issue{issues.length === 1 ? "" : "s"}
          </span>
        ) : (
          authored.length === 0 && <span className="text-xs text-slate-400">no issues</span>
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
          {(issues.length > 0 || authored.length > 0) && (
            <div className="border-t border-amber-200 bg-amber-50/60">
              <button
                type="button"
                onClick={() => setIssuesOpen((v) => !v)}
                className="flex w-full items-center gap-1.5 px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-amber-700 hover:bg-amber-100/60"
              >
                <span>{issuesOpen ? "▾" : "▸"}</span>
                <span>
                  ⚠ Flagged issues ({issues.length}
                  {authored.length > 0 ? ` jury · ${authored.length} human` : ""})
                </span>
                {onLabel && issuesOpen && (
                  <span className="font-normal normal-case">— mark each ✓ valid / ✗ false alarm</span>
                )}
              </button>
              {issuesOpen && (
                <div className="space-y-2 px-4 pb-3">
                  {authored.map((f) => (
                    <AuthoredRow
                      key={f.id}
                      finding={f}
                      onFocusNote={onFocusNote}
                      onRemove={onRemoveAuthored}
                      onPromote={onPromote}
                    />
                  ))}
                  {issues.map((f, i) => (
                    <FindingRow
                      key={f.key ?? i}
                      finding={f}
                      dimension={d.dimension}
                      labelEntry={f.key ? findingLabels[f.key] : undefined}
                      onFocusNote={onFocusNote}
                      onLabel={onLabel}
                      onPromote={onPromote}
                    />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* zone 3: human adjudication */}
          {(onAdjudicate || onAuthorFinding) && (
            <div className="flex flex-wrap items-start gap-x-5 gap-y-2 border-t border-slate-100 px-3 py-2">
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
              {onAuthorFinding && <AuthorFindingForm dimension={d.dimension} onSave={onAuthorFinding} />}
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
  onLabel,
  onAdjudicate,
  onAuthorFinding,
  onRemoveAuthored,
  onPromote,
}: {
  verdict: Verdict;
  adjudication?: Adjudication | null;
  onFocusNote: (noteId: string, quote: string) => void;
  onLabel?: OnLabel;
  onAdjudicate?: (dimension: string, score: number | null, rationale: string) => void;
  onAuthorFinding?: AuthorFinding;
  onRemoveAuthored?: (id: string) => void;
  onPromote?: OnPromote;
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
          onLabel={onLabel}
          onAdjudicate={onAdjudicate}
          onAuthorFinding={onAuthorFinding}
          onRemoveAuthored={onRemoveAuthored}
          onPromote={onPromote}
        />
      ))}
    </div>
  );
}
