import { useState } from "react";
import { api } from "../api";
import type { NoteData, Verdict } from "../types";
import { splitIds, splitPasted } from "../lib";
import {
  Alert,
  Expander,
  HighlightText,
  ScoreBadge,
  Spinner,
  buttonClass,
  inputClass,
  primaryButtonClass,
  textareaClass,
} from "../components/ui";
import VerdictView, { type FocusNote } from "../components/VerdictView";

export default function LiveJudge({ openCase }: { openCase: (caseId: string) => void }) {
  const [summary, setSummary] = useState("");
  const [pasted, setPasted] = useState("");
  const [ids, setIds] = useState("");
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [notes, setNotes] = useState<NoteData[]>([]);
  const [focus, setFocus] = useState<FocusNote>(null);
  const [judging, setJudging] = useState(false);
  const [notice, setNotice] = useState<{ kind: "error" | "warning" | "success"; text: string } | null>(null);
  const [showSave, setShowSave] = useState(false);
  const [saveId, setSaveId] = useState("");

  const judge = async () => {
    setJudging(true);
    setNotice(null);
    try {
      const res = await api.post("/api/judge-adhoc", {
        summary_text: summary,
        note_ids: splitIds(ids),
        pasted_notes: splitPasted(pasted).map((text) => ({ text })),
      });
      setVerdict(res.verdict);
      setNotes(res.notes);
      setFocus(null);
      if (res.missing_note_ids?.length) {
        setNotice({ kind: "warning", text: `Could not fetch: ${res.missing_note_ids.join(", ")}` });
      }
    } catch (e) {
      setNotice({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    } finally {
      setJudging(false);
    }
  };

  const saveAsCase = async () => {
    try {
      const created = await api.post("/api/cases", {
        summary_text: summary,
        case_id: saveId || null,
        note_ids: splitIds(ids),
        pasted_notes: splitPasted(pasted).map((text) => ({ text })),
      });
      setNotice({ kind: "success", text: `Saved case '${created.case_id}' — see Summary Explorer.` });
      setShowSave(false);
      openCase(created.case_id);
    } catch (e) {
      setNotice({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-slate-500">
        Scratchpad — paste or fetch notes, type a summary, and judge it live. Edit the summary and re-judge
        to watch the scores move. Nothing is saved unless you Save as case.
      </p>
      {notice && <Alert kind={notice.kind}>{notice.text}</Alert>}
      <div className="grid gap-4 xl:grid-cols-2">
        {/* left: summary + verdict */}
        <div className="max-h-[46rem] space-y-3 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/60 p-4">
          <div className="text-sm font-semibold text-slate-700">Summary</div>
          <textarea
            className={textareaClass}
            rows={8}
            placeholder="Paste or type the summary to judge…"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
          />
          <div className="flex items-center gap-2">
            <button type="button" className={primaryButtonClass} disabled={judging} onClick={judge}>
              ⚖️ Judge
            </button>
            <button type="button" className={buttonClass} onClick={() => setShowSave((v) => !v)}>
              💾 Save as case
            </button>
            {judging && <Spinner label="Polling the jury…" />}
          </div>
          {showSave && (
            <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-2">
              <input
                className={`${inputClass} !w-64`}
                placeholder="case id (auto if blank)"
                value={saveId}
                onChange={(e) => setSaveId(e.target.value)}
              />
              <button type="button" className={`${primaryButtonClass} !py-1`} onClick={saveAsCase}>
                save
              </button>
            </div>
          )}
          {verdict ? (
            <>
              <div className="flex items-center gap-2 border-t border-slate-200 pt-3">
                <span className="text-sm font-semibold text-slate-700">Verdict</span>
                <span className="text-xs text-slate-500">overall</span>
                <ScoreBadge score={verdict.overall_score} />
              </div>
              <VerdictView
                verdict={verdict}
                onFocusNote={(noteId, quote) => setFocus({ noteId, quote })}
              />
            </>
          ) : (
            <Alert kind="info">Enter a summary and notes, then Judge.</Alert>
          )}
        </div>

        {/* right: reference notes */}
        <div className="max-h-[46rem] space-y-3 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/60 p-4">
          <div className="text-sm font-semibold text-slate-700">Reference notes</div>
          <textarea
            className={textareaClass}
            rows={7}
            placeholder={"Paste note text (separate multiple notes with a line of ---)"}
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
          />
          <textarea
            className={textareaClass}
            rows={2}
            placeholder="…or fetch by Epic note ID (space / comma / newline separated)"
            value={ids}
            onChange={(e) => setIds(e.target.value)}
          />
          <div className="text-xs text-slate-400">
            Pasted text works offline; fetched IDs need JURY_MODE=live + Epic creds.
          </div>
          {notes.length > 0 && (
            <>
              <div className="text-sm font-semibold text-slate-700">Resolved notes</div>
              <div className="space-y-2">
                {notes.map((n) => {
                  const nid = n.document_reference_id;
                  const focused = focus?.noteId === nid;
                  return (
                    <Expander
                      key={nid}
                      title={`${nid} · ${n.metadata?.type || "—"}`}
                      open={focused ? true : undefined}
                      scrollIntoViewWhenOpened
                    >
                      <HighlightText
                        text={n.combined_text || ""}
                        quotes={focused && focus ? [focus.quote] : []}
                      />
                    </Expander>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
