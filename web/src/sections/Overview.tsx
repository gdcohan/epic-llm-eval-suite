import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { OverviewRow, OverviewStats } from "../types";
import { HARM_COLORS, fmtScore, scoreColor } from "../lib";
import { Alert, BarChart, KpiCard, Spinner } from "../components/ui";

type Filter = "all" | "issues" | "severe";

const SEVERITIES = ["low", "moderate", "severe"] as const;

function HarmMatrix({ stats }: { stats: OverviewStats }) {
  const hm = stats.harm_matrix || {};
  const cats = [
    ...stats.harm_categories.filter((c) => c in hm),
    ...Object.keys(hm).filter((c) => !stats.harm_categories.includes(c)),
  ];
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 text-sm font-medium text-slate-600">
        Harm matrix — # cases with ≥1 issue by category × severity
      </div>
      {cats.length === 0 ? (
        <div className="text-sm text-slate-400">
          No harm-tagged findings yet (harm appears on live jury runs).
        </div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
              <th className="py-1.5 pr-3">category</th>
              {SEVERITIES.map((s) => (
                <th key={s} className="py-1.5 pr-3">
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
                  return (
                    <td key={sev} className="py-1.5 pr-3">
                      <span
                        className="inline-block min-w-8 rounded px-2 py-0.5 text-center font-medium"
                        style={v > 0 ? { background: HARM_COLORS[sev], color: "white" } : { color: "#94a3b8" }}
                      >
                        {v}
                      </span>
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
  const [filter, setFilter] = useState<Filter>("all");
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
    let out = [...stats.rows];
    if (filter === "issues") out = out.filter((r) => Number(r.issues) > 0);
    if (filter === "severe") out = out.filter((r) => r.max_harm === "severe");
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
  }, [stats, filter, sortKey, sortAsc]);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!stats) return <Spinner label="loading overview…" />;

  const k = stats.kpis;
  const scoreCols = new Set(["overall", ...stats.dims]);

  const sortBy = (col: string) => {
    if (sortKey === col) setSortAsc((v) => !v);
    else {
      setSortKey(col);
      setSortAsc(true);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <KpiCard label="Cases" value={k.cases} />
        <KpiCard label="Judged" value={k.judged} />
        <KpiCard label="Avg overall" value={k.avg_overall ?? "—"} />
        <KpiCard
          label="With issues"
          value={k.with_issues}
          active={filter === "issues"}
          onClick={k.with_issues ? () => setFilter(filter === "issues" ? "all" : "issues") : undefined}
        />
        <KpiCard
          label="⚠ Severe"
          value={k.severe_cases}
          active={filter === "severe"}
          onClick={k.severe_cases ? () => setFilter(filter === "severe" ? "all" : "severe") : undefined}
        />
        <KpiCard label="Juror splits" value={k.splits} />
      </div>

      {k.judged === 0 ? (
        <Alert kind="info">No judged cases yet — judge some in the Summary Explorer.</Alert>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <BarChart title="Avg score by dimension" data={stats.avg_by_dim} max={5} />
            <BarChart title="Issues by dimension" data={stats.issues_by_dim} color="#f97316" />
          </div>

          <HarmMatrix stats={stats} />

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="mb-3 text-sm font-medium text-slate-600">
              {filter === "all"
                ? "Case scorecard (lower = redder; click a header to sort, a row to open it)"
                : `Case scorecard — only the ${rows.length} case(s) ${filter === "severe" ? "with a severe issue" : "with issues"}`}
              {filter !== "all" && (
                <button type="button" className="ml-3 text-indigo-600 hover:underline" onClick={() => setFilter("all")}>
                  × show all
                </button>
              )}
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
        </>
      )}
    </div>
  );
}
