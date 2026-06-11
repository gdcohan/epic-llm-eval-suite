import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Adjudication, CaseDetail, CaseMeta, Finding } from "../types";
import { fmtScore, splitIds, splitPasted } from "../lib";
import {
  Alert,
  Expander,
  HighlightText,
  ScoreBadge,
  Spinner,
  inputClass,
  primaryButtonClass,
  textareaClass,
} from "../components/ui";
import VerdictView, {
  type AuthoredDraft,
  type ExemplarDraft,
  type FocusNote,
  type LabelPayload,
} from "../components/VerdictView";
import NotesList from "../components/NotesList";

function NewSummaryForm({ onCreated }: { onCreated: (caseId: string) => void }) {
  const [caseId, setCaseId] = useState("");
  const [summary, setSummary] = useState("");
  const [noteIds, setNoteIds] = useState("");
  const [pasted, setPasted] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await api.post("/api/cases", {
        summary_text: summary,
        case_id: caseId || null,
        note_ids: splitIds(noteIds),
        pasted_notes: splitPasted(pasted).map((text) => ({ text })),
      });
      setCaseId("");
      setSummary("");
      setNoteIds("");
      setPasted("");
      onCreated(created.case_id);
    } catch (e) {
      setError(`Could not create case: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Expander title="➕ New summary">
      <div className="space-y-3">
        <div>
          <input
            className={inputClass}
            disabled
            placeholder="Fetch a summary by Epic ID — coming soon: pull a GenAI summary and its source notes from Epic"
            title="Future: resolve a summary and its reference notes via FHIR provenance."
          />
          <div className="mt-1 text-xs text-slate-400">For now, build a case manually:</div>
        </div>
        <input
          className={inputClass}
          placeholder="Case name (auto-generated if blank)"
          value={caseId}
          onChange={(e) => setCaseId(e.target.value)}
        />
        <textarea
          className={textareaClass}
          rows={5}
          placeholder="Paste the GenAI summary…"
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
        />
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <textarea
              className={textareaClass}
              rows={4}
              placeholder={"Reference note IDs\nexArV…  ex.6rD…\n(space / comma / newline separated)"}
              value={noteIds}
              onChange={(e) => setNoteIds(e.target.value)}
            />
            <div className="mt-1 text-xs text-slate-400">Fetched + cleaned via FHIR (needs live Epic creds).</div>
          </div>
          <div>
            <textarea
              className={textareaClass}
              rows={4}
              placeholder={"…or paste note text\n---\nseparate multiple notes with a line of ---"}
              value={pasted}
              onChange={(e) => setPasted(e.target.value)}
            />
            <div className="mt-1 text-xs text-slate-400">Escape hatch: no FHIR needed. Split notes with ---.</div>
          </div>
        </div>
        {error && <Alert kind="error">{error}</Alert>}
        <button type="button" className={primaryButtonClass} disabled={busy} onClick={submit}>
          {busy ? "Creating…" : "Create case"}
        </button>
      </div>
    </Expander>
  );
}

export default function Explorer({
  selectedCase,
  setSelectedCase,
}: {
  selectedCase: string | null;
  setSelectedCase: (id: string | null, opts?: { replace?: boolean }) => void;
}) {
  const [casesList, setCasesList] = useState<CaseMeta[] | null>(null);
  const [detail, setDetail] = useState<CaseDetail | null>(null);
  const [focus, setFocus] = useState<FocusNote>(null);
  const [judging, setJudging] = useState(false);
  const [notice, setNotice] = useState<{ kind: "error" | "warning" | "success"; text: string } | null>(null);
  const [adjudicator, setAdjudicator] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(
    () => localStorage.getItem("explorer.sidebar") !== "collapsed",
  );
  // notes column starts collapsed; a ↪ source click expands it
  const [notesOpen, setNotesOpen] = useState(false);
  // draggable split between the jury and notes columns (fraction for the left)
  const [split, setSplit] = useState(() => {
    const v = parseFloat(localStorage.getItem("explorer.split") || "");
    return Number.isFinite(v) && v >= 0.3 && v <= 0.75 ? v : 0.6;
  });
  const [dragging, setDragging] = useState(false);
  const splitRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!dragging) return;
    const onMove = (e: MouseEvent) => {
      const rect = splitRef.current?.getBoundingClientRect();
      if (!rect || rect.width === 0) return;
      setSplit(Math.min(0.75, Math.max(0.3, (e.clientX - rect.left) / rect.width)));
    };
    const onUp = () => setDragging(false);
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
  }, [dragging]);

  useEffect(() => {
    if (!dragging) localStorage.setItem("explorer.split", String(split));
  }, [dragging, split]);

  const toggleSidebar = () =>
    setSidebarOpen((open) => {
      localStorage.setItem("explorer.sidebar", open ? "collapsed" : "open");
      return !open;
    });

  const loadCases = useCallback(async () => {
    const list: CaseMeta[] = await api.get("/api/cases");
    setCasesList(list);
    return list;
  }, []);

  useEffect(() => {
    loadCases()
      .then((list) => {
        if (list.length && !list.some((c) => c.case_id === selectedCase)) {
          // default selection, not a user action — don't create a history entry
          setSelectedCase(list[0].case_id, { replace: true });
        }
      })
      .catch((e) => setNotice({ kind: "error", text: String(e) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedCase) {
      setDetail(null);
      return;
    }
    setDetail(null);
    setFocus(null);
    setNotesOpen(false);
    setNotice(null);
    api
      .get(`/api/cases/${encodeURIComponent(selectedCase)}`)
      .then((d: CaseDetail) => {
        setDetail(d);
        setAdjudicator((prev) => prev || d.adjudication?.adjudicator || "");
      })
      .catch((e) => setNotice({ kind: "error", text: String(e) }));
  }, [selectedCase]);

  const runJury = async () => {
    if (!selectedCase) return;
    setJudging(true);
    setNotice(null);
    try {
      const res = await api.post(`/api/cases/${encodeURIComponent(selectedCase)}/judge`);
      setDetail((d) => (d ? { ...d, verdict: res.verdict } : d));
      if (res.missing_note_ids?.length) {
        setNotice({
          kind: "warning",
          text: `Could not fetch ${res.missing_note_ids.length} note(s): ${res.missing_note_ids.join(", ")}`,
        });
      }
      // refresh notes (judging may have fetched some) and the sidebar score
      const d: CaseDetail = await api.get(`/api/cases/${encodeURIComponent(selectedCase)}`);
      setDetail(d);
      await loadCases();
    } catch (e) {
      setNotice({ kind: "error", text: `Judging failed: ${e instanceof Error ? e.message : e}` });
    } finally {
      setJudging(false);
    }
  };

  const labelFinding = async (
    finding: Finding & { key?: string },
    dimension: string,
    payload: LabelPayload,
  ) => {
    if (!selectedCase || !finding.key) return;
    const adj: Adjudication = await api.post(
      `/api/cases/${encodeURIComponent(selectedCase)}/finding-label`,
      {
        dimension,
        member: finding.member,
        summary_quote: finding.summary_quote,
        note_quote: finding.note_quote,
        note_id: finding.note_id,
        explanation: finding.explanation,
        ...payload,
      },
    );
    setDetail((d) => (d ? { ...d, adjudication: adj } : d));
  };

  const promoteExemplar = async (draft: ExemplarDraft) => {
    try {
      await api.post("/api/exemplars", draft);
      setNotice({
        kind: "success",
        text: `★ Promoted to exemplar (${draft.dimension}) — it now teaches the jury via the prompt. Manage in Jury Config.`,
      });
    } catch (e) {
      setNotice({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  };

  const authorFinding = async (dimension: string, draft: AuthoredDraft) => {
    if (!selectedCase) return;
    try {
      const adj: Adjudication = await api.post(
        `/api/cases/${encodeURIComponent(selectedCase)}/authored-finding`,
        { dimension, ...draft, author: adjudicator },
      );
      setDetail((d) => (d ? { ...d, adjudication: adj } : d));
    } catch (e) {
      setNotice({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  };

  const removeAuthored = async (findingId: string) => {
    if (!selectedCase) return;
    const adj: Adjudication = await api.del(
      `/api/cases/${encodeURIComponent(selectedCase)}/authored-finding/${encodeURIComponent(findingId)}`,
    );
    setDetail((d) => (d ? { ...d, adjudication: adj } : d));
  };

  const adjudicateDimension = async (dimension: string, score: number | null, rationale: string) => {
    if (!selectedCase) return;
    const adj: Adjudication = await api.post(
      `/api/cases/${encodeURIComponent(selectedCase)}/adjudicate-dimension`,
      { dimension, score, rationale, adjudicator },
    );
    setDetail((d) => (d ? { ...d, adjudication: adj } : d));
    setNotice({ kind: "success", text: `Saved adjudication for ${dimension}.` });
  };

  const onCreated = async (caseId: string) => {
    await loadCases();
    setSelectedCase(caseId);
    setNotice({ kind: "success", text: `Created case '${caseId}'.` });
  };

  const verdict = detail?.verdict ?? null;
  const flaggedQuotes =
    verdict?.dimensions.flatMap((d) =>
      d.findings.filter((f) => f.type === "issue").map((f) => f.summary_quote),
    ) ?? [];

  return (
    <div className="flex gap-5">
      {/* sidebar: ingested summaries (collapsible to give the columns room) */}
      {!sidebarOpen ? (
        <button
          type="button"
          title="expand case list"
          onClick={toggleSidebar}
          className="flex h-fit shrink-0 flex-col items-center gap-2 rounded-lg border border-slate-200 bg-white px-1.5 py-3 text-slate-500 shadow-sm hover:bg-slate-50 hover:text-slate-700"
        >
          <span>»</span>
          <span className="text-xs font-medium [writing-mode:vertical-rl]">
            Cases ({casesList?.length ?? 0})
          </span>
        </button>
      ) : (
      <aside className="w-64 shrink-0">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-semibold text-slate-700">Ingested summaries</span>
          <button
            type="button"
            title="collapse case list"
            onClick={toggleSidebar}
            className="rounded px-1.5 py-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
          >
            «
          </button>
        </div>
        {casesList === null ? (
          <Spinner />
        ) : casesList.length === 0 ? (
          <div className="text-sm text-slate-400">none yet — use ➕ New summary</div>
        ) : (
          <div className="space-y-1">
            {casesList.map((c) => (
              <button
                key={c.case_id}
                type="button"
                onClick={() => setSelectedCase(c.case_id)}
                className={`flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm ${
                  c.case_id === selectedCase
                    ? "bg-indigo-600 text-white"
                    : "text-slate-700 hover:bg-slate-100"
                }`}
              >
                <span className="min-w-0 flex-1 truncate">{c.case_id}</span>
                <span className={c.case_id === selectedCase ? "text-indigo-200" : "text-slate-400"}>
                  {c.judged ? fmtScore(c.overall) : "—"}
                </span>
              </button>
            ))}
          </div>
        )}
      </aside>
      )}

      <div className="min-w-0 flex-1 space-y-4">
        <NewSummaryForm onCreated={onCreated} />
        {notice && <Alert kind={notice.kind}>{notice.text}</Alert>}

        {!selectedCase || !detail ? (
          casesList?.length === 0 ? (
            <Alert kind="info">No summaries yet. Use ➕ New summary to create one.</Alert>
          ) : (
            <Spinner label="loading case…" />
          )
        ) : (
          <div ref={splitRef} className={`flex gap-2 ${dragging ? "select-none" : ""}`}>
            {/* col 1: summary + judge synopsis */}
            <div
              className="max-h-[46rem] min-w-0 flex-1 space-y-4 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/60 p-4"
              style={notesOpen ? { flex: "none", width: `${split * 100}%` } : undefined}
            >
              <div>
                <span className="text-base font-semibold text-slate-800">{detail.case.case_id}</span>
                <span className="ml-2 text-xs text-slate-500">
                  · source: {detail.case.summary?.source || "—"}
                </span>
              </div>
              <div>
                <div className="mb-1 text-sm font-semibold text-slate-700">Summary</div>
                <div className="rounded-lg border border-slate-200 bg-white p-3">
                  <HighlightText text={detail.case.summary?.text || ""} quotes={flaggedQuotes} />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <button type="button" className={primaryButtonClass} disabled={judging} onClick={runJury}>
                  {verdict ? "↻ Re-run jury" : "▶ Run jury"}
                </button>
                {judging && <Spinner label="Polling the jury…" />}
              </div>

              {!verdict ? (
                <Alert kind="info">Not judged yet — click Run jury.</Alert>
              ) : (
                <>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-slate-700">Judge synopsis</span>
                    <span className="text-xs text-slate-500">overall</span>
                    <ScoreBadge score={verdict.overall_score} />
                  </div>
                  <input
                    className={inputClass}
                    placeholder="Adjudicator — your name (for the overrides below)"
                    value={adjudicator}
                    onChange={(e) => setAdjudicator(e.target.value)}
                  />
                  <VerdictView
                    verdict={verdict}
                    adjudication={detail.adjudication}
                    onFocusNote={(noteId, quote) => {
                      setFocus({ noteId, quote });
                      setNotesOpen(true);
                    }}
                    onLabel={labelFinding}
                    onAdjudicate={adjudicateDimension}
                    onAuthorFinding={authorFinding}
                    onRemoveAuthored={removeAuthored}
                    onPromote={promoteExemplar}
                  />
                </>
              )}
            </div>

            {/* col 2: reference notes (collapsed by default; ↪ source expands) */}
            {!notesOpen ? (
              <button
                type="button"
                title="expand reference notes"
                onClick={() => setNotesOpen(true)}
                className="flex h-fit shrink-0 flex-col items-center gap-2 rounded-lg border border-slate-200 bg-white px-1.5 py-3 text-slate-500 shadow-sm hover:bg-slate-50 hover:text-slate-700"
              >
                <span>«</span>
                <span className="text-xs font-medium [writing-mode:vertical-rl]">
                  Reference notes ({detail.case.source_note_ids?.length ?? 0})
                </span>
              </button>
            ) : (
              <>
                <div
                  title="drag to resize"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    setDragging(true);
                  }}
                  className={`w-1.5 shrink-0 cursor-col-resize self-stretch rounded-full ${
                    dragging ? "bg-indigo-500" : "bg-slate-200 hover:bg-indigo-300"
                  }`}
                />
              <div className="max-h-[46rem] min-w-0 flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/60 p-4">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-semibold text-slate-700">
                    Reference notes ({detail.case.source_note_ids?.length ?? 0})
                  </span>
                  <button
                    type="button"
                    title="collapse reference notes"
                    onClick={() => setNotesOpen(false)}
                    className="rounded px-1.5 py-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                  >
                    »
                  </button>
                </div>
                <NotesList
                  noteIds={detail.case.source_note_ids || []}
                  notes={detail.notes}
                  focus={focus}
                  onFlagMissing={async (draft) => {
                    await authorFinding("comprehensiveness", draft);
                    setNotice({
                      kind: "success",
                      text: "Flagged span as ✋ missing from summary (comprehensiveness).",
                    });
                  }}
                />
              </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
