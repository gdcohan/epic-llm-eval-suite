import { useEffect, useState } from "react";
import { api } from "../api";
import type { PrecisionStats } from "../types";
import { Alert, KpiCard, Spinner } from "../components/ui";

export default function Calibrate() {
  const [stats, setStats] = useState<PrecisionStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get("/api/precision").then(setStats).catch((e) => setError(String(e)));
  }, []);

  if (error) return <Alert kind="error">{error}</Alert>;
  if (!stats) return <Spinner label="loading…" />;

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-800">Finding-level calibration (precision)</h2>
        <p className="mt-1 text-sm text-slate-500">
          Precision = of the jury's flagged findings you reviewed, how many were valid. Label findings in
          the Summary Explorer (✓ valid / ✗ false alarm). Recall (issues the jury missed) is a planned next
          step.
        </p>
      </div>

      {!stats.labeled_cases && !stats.total_authored ? (
        <Alert kind="info">
          No labeled findings yet. In the Summary Explorer, run the jury on a case and mark each issue ✓
          valid / ✗ false alarm — or ✋ flag issues the jury missed.
        </Alert>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3">
            <KpiCard label="Labeled cases" value={stats.labeled_cases} />
            <KpiCard label="Labeled findings" value={stats.total_labeled} />
            <KpiCard label="Overall precision" value={stats.overall_precision ?? "—"} />
            <KpiCard label="✋ Human-flagged missed" value={stats.total_authored} />
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                  {["dimension", "labeled", "validated", "false alarms", "precision", "✋ missed (human)"].map((h) => (
                    <th key={h} className="py-1.5 pr-3">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(stats.per_dimension).map(([dim, v]) => (
                  <tr key={dim} className="border-t border-slate-100 text-slate-700">
                    <td className="py-1.5 pr-3 font-medium">{dim}</td>
                    <td className="py-1.5 pr-3">{v.labeled}</td>
                    <td className="py-1.5 pr-3">{v.validated}</td>
                    <td className="py-1.5 pr-3">{v.false_alarms}</td>
                    <td className="py-1.5 pr-3">{v.precision ?? "—"}</td>
                    <td className="py-1.5 pr-3">{v.authored_missed || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {stats.false_alarms.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-2 text-sm font-medium text-slate-700">
                False alarms (jury flagged, you rejected) — the tuning signal
              </div>
              <ul className="space-y-1.5 text-xs text-slate-600">
                {stats.false_alarms.map((fa, i) => (
                  <li key={i}>
                    <code className="rounded bg-slate-100 px-1">{fa.case}</code> · <b>{fa.dimension}</b> —
                    summary: <i>“{fa.summary_quote || "—"}”</i> · note: <i>“{fa.note_quote || "—"}”</i>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}
