import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { OverviewRow, OverviewStats } from "../types";
import { HARM_COLORS, fmtScore, scoreColor } from "../lib";
import { Alert, BarChart, KpiCard, Spinner } from "../components/ui";

const SEVERITIES = ["low", "moderate", "severe"] as const;

type Picker = { caseIds: string[]; x: number; y: number } | null;

/** Anchored dropdown for choosing among several matching cases. */
function CasePicker({
  picker,
  rows,
  onPick,
  onClose,
}: {
  picker: NonNullable<Picker>;
  rows: OverviewRow[];
  onPick: (caseId: string) => void;
  onClose: () => void;
}) {
  const byId = new Map(rows.map((r) => [r.case, r]));
  // keep the dropdown on-screen for anchors near the right edge
  const left = Math.min(picker.x, Math.max(8, window.innerWidth - 296));
  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div
        className="fixed z-50 w-72 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg"
        style={{ left, top: picker.y }}
      >
        <div className="border-b border-slate-100 px-3 py-1.5 text-xs font-medium text-slate-500">
          {picker.caseIds.length} matching cases — pick one
        </div>
        {picker.caseIds.map((cid) => {
          const r = byId.get(cid);
          return (
            <button
              key={cid}
              type="button"
              className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-indigo-50"
              onClick={() => onPick(cid)}
            >
              <span className="min-w-0 flex-1 truncate text-slate-700">{cid}</span>
              {r?.max_harm && (
                <span
                  className="rounded px-1.5 py-0.5 text-[11px] font-medium text-white"
                  style={{ background: HARM_COLORS[r.max_harm] ?? "#6c757d" }}
                >
                  {r.max_harm}
                </span>
              )}
              <span
                className="min-w-10 rounded px-1.5 py-0.5 text-center text-[11px] font-medium text-white"
                style={{ background: scoreColor(typeof r?.overall === "number" ? r.overall : null) }}
              >
                {fmtScore(typeof r?.overall === "number" ? r.overall : null)}
              </span>
            </button>
          );
        })}
      </div>
    </>
  );
}

function HarmMatrix({
  stats,
  onPickCell,
}: {
  stats: OverviewStats;
  onPickCell: (caseIds: string[], e: React.MouseEvent<HTMLElement>) => void;
}) {
  const hm = stats.harm_matrix || {};
  const hmCases = stats.harm_matrix_cases || {};
  const cats = [
    ...stats.harm_categories.filter((c) => c in hm),
    ...Object.keys(hm).filter((c) => !stats.harm_categories.includes(c)),
  ];
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 text-sm font-medium text-slate-600">
        Harm matrix — # cases with ≥1 issue by category × severity (click a cell to open the case)
      </div>
      {cats.length === 0 ? (
        <div className="text-sm text-slate-400">
          No harm-tagged findings yet (harm appears on live jury runs).
        </div>
      ) : (
        <table className="w-full table-fixed text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="w-[40%] py-1.5 pr-3">category</th>
              {SEVERITIES.map((s) => (
                <th key={s} className="w-[20%] py-1.5 pr-3">
                  {s}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cats.map((cat) => (
              <tr key={cat} className="border-t border-slate-100">
                <td className="py-1.5 pr-3 text-slate-700">{cat}</td>
                {SEVERITIES.map((sev) => {
                  const v = hm[cat]?.[sev] ?? 0;
                  const caseIds = hmCases[cat]?.[sev] ?? [];
                  return (
                    <td key={sev} className="py-1.5 pr-3">
                      {v > 0 ? (
                        <button
                          type="button"
                          title={caseIds.join(", ")}
                          className="inline-block min-w-8 cursor-pointer rounded px-2 py-0.5 text-center font-medium text-white hover:ring-2 hover:ring-indigo-300"
                          style={{ background: HARM_COLORS[sev] }}
                          onClick={(e) => onPickCell(caseIds, e)}
                        >
                          {v}
                        </button>
                      ) : (
                        <span className="inline-block min-w-8 px-2 py-0.5 text-center text-slate-300">0</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function Overview({ openCase }: { openCase: (caseId: string) => void }) {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picker, setPicker] = useState<Picker>(null);
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortAsc, setSortAsc] = useState(true);

  useEffect(() => {
    api.get("/api/overview").then(setStats).catch((e) => setError(String(e)));
  }, []);

  const columns = useMemo(() => {
    if (!stats) return [];
    return ["case", "overall", ...stats.dims, "issues", "max_harm", "adjudicated", "agreement"];
  }, [stats]);

  const rows = useMemo(() => {
    if (!stats) return [];
    const out = [...stats.rows];
    if (sortKey) {
      out.sort((a, b) => {
        const av = a[sortKey as keyof OverviewRow];
        const bv = b[sortKey as keyof OverviewRow];
        if (av == null && bv == null) return 0;
        if (av == null) return 1;
        if (bv == null) return -1;
        const cmp =
          typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
        return sortAsc ? cmp : -cmp;
      });
    }
    return out;
  }, [stats, sortKey, sortAsc]);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!stats) return <Spinner label="loading overview…" />;

  const k = stats.kpis;
  const scoreCols = new Set(["overall", ...stats.dims]);

  // Jump straight to the Explorer for one match; anchored picker for several.
  const choose = (caseIds: string[], e: React.MouseEvent<HTMLElement>) => {
    if (caseIds.length === 0) return;
    if (caseIds.length === 1) {
      openCase(caseIds[0]);
      return;
    }
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    setPicker({ caseIds, x: r.left, y: r.bottom + 4 });
  };

  const issueCaseIds = stats.rows.filter((r) => Number(r.issues) > 0).map((r) => r.case);
  const severeCaseIds = stats.rows.filter((r) => r.max_harm === "severe").map((r) => r.case);

  const sortBy = (col: string) => {
    if (sortKey === col) setSortAsc((v) => !v);
    else {
      setSortKey(col);
      setSortAsc(true);
    }
  };

  return (
    <div className="space-y-6">
      {picker && (
        <CasePicker
          picker={picker}
          rows={stats.rows}
          onPick={(cid) => {
            setPicker(null);
            openCase(cid);
          }}
          onClose={() => setPicker(null)}
        />
      )}

      <div className="grid grid-cols-3 gap-3">
        <KpiCard label="Avg overall" value={k.avg_overall ?? "—"} />
        <KpiCard
          label="With issues"
          value={k.with_issues}
          onClick={issueCaseIds.length ? (e) => choose(issueCaseIds, e) : undefined}
        />
        <KpiCard
          label="⚠ Severe"
          value={k.severe_cases}
          onClick={severeCaseIds.length ? (e) => choose(severeCaseIds, e) : undefined}
        />
      </div>

      {k.judged === 0 ? (
        <Alert kind="info">No judged cases yet — judge some in the Summary Explorer.</Alert>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <BarChart title="Avg score by dimension" data={stats.avg_by_dim} max={5} />
            <HarmMatrix stats={stats} onPickCell={choose} />
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-3 text-sm font-medium text-slate-600">
              Case scorecard (lower = redder; click a header to sort, a row to open it)
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                    {columns.map((col) => (
                      <th
                        key={col}
                        className="cursor-pointer select-none whitespace-nowrap py-1.5 pr-3 hover:text-slate-700"
                        onClick={() => sortBy(col)}
                      >
                        {col}
                        {sortKey === col ? (sortAsc ? " ▲" : " ▼") : ""}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr
                      key={r.case}
                      className="cursor-pointer border-t border-slate-100 hover:bg-indigo-50/50"
                      onClick={() => openCase(r.case)}
                    >
                      {columns.map((col) => {
                        const v = r[col as keyof OverviewRow];
                        if (scoreCols.has(col)) {
                          const num = typeof v === "number" ? v : null;
                          return (
                            <td key={col} className="py-1.5 pr-3">
                              <span
                                className="inline-block min-w-12 rounded px-2 py-0.5 text-center font-medium text-white"
                                style={{ background: scoreColor(num) }}
                              >
                                {fmtScore(num)}
                              </span>
                            </td>
                          );
                        }
                        if (col === "max_harm") {
                          const harm = typeof v === "string" ? v : "";
                          return (
                            <td key={col} className="py-1.5 pr-3">
                              {harm ? (
                                <span
                                  className="inline-block rounded px-2 py-0.5 text-center font-medium text-white"
                                  style={{ background: HARM_COLORS[harm] ?? "#6c757d" }}
                                >
                                  {harm}
                                </span>
                              ) : (
                                <span className="text-slate-400">—</span>
                              )}
                            </td>
                          );
                        }
                        return (
                          <td key={col} className="whitespace-nowrap py-1.5 pr-3 text-slate-700">
                            {v == null || v === "" ? <span className="text-slate-400">—</span> : String(v)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="text-xs text-slate-400">
            {k.cases} case{k.cases === 1 ? "" : "s"} · {k.judged} judged · {k.splits} juror split
            {k.splits === 1 ? "" : "s"}
          </div>
        </>
      )}
    </div>
  );
}
