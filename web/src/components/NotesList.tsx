import { useEffect, useState } from "react";
import type { NoteData } from "../types";
import type { AuthoredDraft, FocusNote } from "./VerdictView";
import { HARM_CATEGORIES } from "../lib";
import { Expander, HighlightText, buttonClass, inputClass, primaryButtonClass } from "./ui";

function RawFhir({ note }: { note: NoteData }) {
  const [show, setShow] = useState(false);
  if (note.resolved_via === "manual" || !note.raw_document_reference) return null;
  return (
    <div className="mt-2">
      <button type="button" className={`${buttonClass} !px-2 !py-1 !text-xs`} onClick={() => setShow((v) => !v)}>
        {show ? "hide" : "show"} raw FHIR DocumentReference
      </button>
      {show && (
        <pre className="mt-2 max-h-80 overflow-auto rounded-lg bg-slate-900 p-3 text-[11px] leading-relaxed text-slate-100">
          {JSON.stringify(note.raw_document_reference, null, 2)}
        </pre>
      )}
    </div>
  );
}

type Selection = { noteId: string; quote: string; x: number; y: number };

/** Floating affordance + mini-form for flagging a selected note span as
 * missing from the summary (creates a comprehensiveness authored finding). */
function SelectionFlagger({
  sel,
  onSave,
  onDismiss,
}: {
  sel: Selection;
  onSave: (draft: AuthoredDraft) => void;
  onDismiss: () => void;
}) {
  const [formOpen, setFormOpen] = useState(false);
  const [explanation, setExplanation] = useState("");
  const [harmCategory, setHarmCategory] = useState("");
  const [harmSeverity, setHarmSeverity] = useState("");
  const left = Math.min(Math.max(8, sel.x - 160), window.innerWidth - 336);

  return (
    <div data-flag-pop className="fixed z-50" style={{ left, top: sel.y }}>
      {!formOpen ? (
        <button
          type="button"
          className="rounded-lg bg-slate-800 px-2.5 py-1.5 text-xs font-medium text-white shadow-lg hover:bg-slate-700"
          onClick={() => setFormOpen(true)}
        >
          ✋ missing from summary
        </button>
      ) : (
        <div className="w-80 space-y-2 rounded-xl border border-slate-200 bg-white p-3 shadow-lg">
          <div className="max-h-16 overflow-hidden text-xs italic text-slate-500">
            “{sel.quote.length > 160 ? `${sel.quote.slice(0, 160)}…` : sel.quote}”
          </div>
          <input
            className={inputClass}
            placeholder="why it matters (optional)"
            value={explanation}
            onChange={(e) => setExplanation(e.target.value)}
          />
          <div className="flex flex-wrap items-center gap-2">
            <select
              className={`${inputClass} !w-auto !py-1`}
              value={harmCategory}
              onChange={(e) => setHarmCategory(e.target.value)}
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
              value={harmSeverity}
              onChange={(e) => setHarmSeverity(e.target.value)}
            >
              <option value="">severity…</option>
              {["low", "moderate", "severe"].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              className={`${primaryButtonClass} !px-2.5 !py-1 !text-xs`}
              onClick={() => {
                onSave({
                  explanation,
                  note_quote: sel.quote,
                  note_id: sel.noteId,
                  harm_category: harmCategory,
                  harm_severity: harmSeverity,
                });
                onDismiss();
              }}
            >
              Flag as missing
            </button>
            <button type="button" className={`${buttonClass} !px-2.5 !py-1 !text-xs`} onClick={onDismiss}>
              cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Reference notes, ordered by the case's note-ID list, with the focused note
 * (from a finding's ↪ source button) opened and its quote highlighted. When
 * `onFlagMissing` is given, selecting a span inside a note offers
 * "✋ missing from summary" (span-level omission flagging). */
export default function NotesList({
  noteIds,
  notes,
  focus,
  onFlagMissing,
  missingHint = "not fetched yet (needs Epic creds; run the jury to fetch)",
}: {
  noteIds: string[];
  notes: NoteData[];
  focus: FocusNote;
  onFlagMissing?: (draft: AuthoredDraft) => void;
  missingHint?: string;
}) {
  const byId = new Map(notes.map((n) => [n.document_reference_id, n]));
  const [sel, setSel] = useState<Selection | null>(null);

  // dismiss the flagger when clicking anywhere outside it (a fresh selection
  // re-arms it via the note's onMouseUp, which fires after this)
  useEffect(() => {
    if (!sel) return;
    const onDown = (e: MouseEvent) => {
      if (!(e.target as Element | null)?.closest?.("[data-flag-pop]")) setSel(null);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [sel]);

  const captureSelection = (noteId: string, container: HTMLElement) => {
    if (!onFlagMissing) return;
    const s = window.getSelection();
    if (!s || s.isCollapsed || s.rangeCount === 0) return;
    const quote = s.toString().trim();
    if (!quote) return;
    const range = s.getRangeAt(0);
    if (!container.contains(range.commonAncestorContainer)) return;
    const r = range.getBoundingClientRect();
    setSel({ noteId, quote, x: r.left + r.width / 2, y: r.bottom + 6 });
  };

  return (
    <div className="space-y-2">
      {sel && onFlagMissing && (
        <SelectionFlagger sel={sel} onSave={onFlagMissing} onDismiss={() => setSel(null)} />
      )}
      {onFlagMissing && notes.length > 0 && (
        <div className="text-xs text-slate-400">
          Tip: select a span in a note to flag it as ✋ missing from the summary.
        </div>
      )}
      {noteIds.map((nid) => {
        const note = byId.get(nid);
        if (!note) {
          return (
            <div key={nid} className="text-sm text-slate-500">
              <code className="rounded bg-slate-100 px-1">{nid}</code> — <i>{missingHint}</i>
            </div>
          );
        }
        const md = note.metadata || {};
        const manual = note.resolved_via === "manual";
        const focused = focus?.noteId === nid;
        return (
          <Expander
            key={nid}
            title={`${manual ? "📝 " : ""}${nid} · ${md.type || "—"} · ${md.date || "—"}`}
            open={focused ? true : undefined}
            scrollIntoViewWhenOpened
          >
            <div onMouseUp={(e) => captureSelection(nid, e.currentTarget)}>
              <HighlightText text={note.combined_text || ""} quotes={focused && focus ? [focus.quote] : []} />
            </div>
            <RawFhir note={note} />
          </Expander>
        );
      })}
    </div>
  );
}
