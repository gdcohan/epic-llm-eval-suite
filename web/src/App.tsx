import { useEffect, useState } from "react";
import { api } from "./api";
import type { PanelInfo } from "./types";
import Overview from "./sections/Overview";
import Explorer from "./sections/Explorer";
import JuryConfig from "./sections/JuryConfig";
import LiveJudge from "./sections/LiveJudge";
import Calibrate from "./sections/Calibrate";

const SECTIONS = ["Overview", "Summary Explorer", "Jury Config", "Live Judge", "Calibrate"] as const;
type Section = (typeof SECTIONS)[number];

export default function App() {
  const [section, setSection] = useState<Section>("Overview");
  const [selectedCase, setSelectedCase] = useState<string | null>(null);
  const [panel, setPanel] = useState<PanelInfo | null>(null);

  useEffect(() => {
    api.get("/api/panel").then(setPanel).catch(() => setPanel(null));
  }, []);

  const openCase = (caseId: string) => {
    setSelectedCase(caseId);
    setSection("Summary Explorer");
  };

  const live = panel?.mode === "live";

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-4 gap-y-1 px-6 py-3">
          <h1 className="text-lg font-bold tracking-tight text-slate-900">Jury Explorer</h1>
          {panel && (
            <span className="text-xs text-slate-500">
              {live ? "🟢 live" : "🟡 stub"} ·{" "}
              {live ? panel.members.join(", ") : "offline stub panel"}
            </span>
          )}
          {panel && !live && (
            <span className="text-xs text-slate-400">
              Stub mode: deterministic placeholder scores. Set JURY_MODE=live (+ API keys) for real
              judgments.
            </span>
          )}
        </div>
        <nav className="mx-auto flex max-w-7xl gap-1 px-6">
          {SECTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSection(s)}
              className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
                section === s
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
              }`}
            >
              {s}
            </button>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6">
        {section === "Overview" && <Overview openCase={openCase} />}
        {section === "Summary Explorer" && (
          <Explorer selectedCase={selectedCase} setSelectedCase={setSelectedCase} />
        )}
        {section === "Jury Config" && <JuryConfig />}
        {section === "Live Judge" && <LiveJudge openCase={openCase} />}
        {section === "Calibrate" && <Calibrate />}
      </main>
    </div>
  );
}
