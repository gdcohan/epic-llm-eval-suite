import { useState } from "react";
import type { NoteData } from "../types";
import type { FocusNote } from "./VerdictView";
import { Expander, HighlightText, buttonClass } from "./ui";

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

/** Reference notes, ordered by the case's note-ID list, with the focused note
 * (from a finding's ↪ source button) opened and its quote highlighted. */
export default function NotesList({
  noteIds,
  notes,
  focus,
  missingHint = "not fetched yet (needs Epic creds; run the jury to fetch)",
}: {
  noteIds: string[];
  notes: NoteData[];
  focus: FocusNote;
  missingHint?: string;
}) {
  const byId = new Map(notes.map((n) => [n.document_reference_id, n]));
  return (
    <div className="space-y-2">
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
            <HighlightText text={note.combined_text || ""} quotes={focused && focus ? [focus.quote] : []} />
            <RawFhir note={note} />
          </Expander>
        );
      })}
    </div>
  );
}
