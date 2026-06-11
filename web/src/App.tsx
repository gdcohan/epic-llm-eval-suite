import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { PanelInfo } from "./types";
import Overview from "./sections/Overview";
import Explorer from "./sections/Explorer";
import JuryConfig from "./sections/JuryConfig";
import LiveJudge from "./sections/LiveJudge";
import Calibrate from "./sections/Calibrate";

const SECTIONS = ["Overview", "Summary Explorer", "Jury Config", "Live Judge", "Calibrate"] as const;
type Section = (typeof SECTIONS)[number];

type Route = { section: Section; caseId: string | null };

const SECTION_PATHS: Record<Section, string> = {
  Overview: "/",
  "Summary Explorer": "/explorer",
  "Jury Config": "/config",
  "Live Judge": "/live",
  Calibrate: "/calibrate",
};

function parseRoute(pathname: string): Route {
  if (pathname === "/explorer" || pathname.startsWith("/explorer/")) {
    const caseId = decodeURIComponent(pathname.slice("/explorer/".length));
    return { section: "Summary Explorer", caseId: caseId || null };
  }
  const section = (Object.keys(SECTION_PATHS) as Section[]).find(
    (s) => SECTION_PATHS[s] === pathname,
  );
  return { section: section ?? "Overview", caseId: null };
}

function routePath(route: Route): string {
  if (route.section === "Summary Explorer" && route.caseId) {
    return `/explorer/${encodeURIComponent(route.caseId)}`;
  }
  return SECTION_PATHS[route.section];
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.pathname));
  const [panel, setPanel] = useState<PanelInfo | null>(null);
  // remember the last viewed case so re-entering the Explorer tab restores it
  const lastCase = useRef<string | null>(route.caseId);

  const refreshPanel = () => {
    api.get("/api/panel").then(setPanel).catch(() => setPanel(null));
  };

  useEffect(() => {
    refreshPanel();
    // normalize unknown initial paths (e.g. /nonsense) without adding an entry
    history.replaceState(null, "", routePath(parseRoute(window.location.pathname)));
    const onPop = () => setRoute(parseRoute(window.location.pathname));
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  useEffect(() => {
    if (route.caseId) lastCase.current = route.caseId;
  }, [route.caseId]);

  /** All in-app navigation funnels through here so Back unwinds it step by step. */
  const navigate = (next: Route, replace = false) => {
    const path = routePath(next);
    if (path !== window.location.pathname) {
      if (replace) history.replaceState(null, "", path);
      else history.pushState(null, "", path);
    }
    setRoute(next);
  };

  const openCase = (caseId: string) => navigate({ section: "Summary Explorer", caseId });

  const setSelectedCase = (caseId: string | null, opts?: { replace?: boolean }) =>
    navigate({ section: "Summary Explorer", caseId }, opts?.replace);

  const openSection = (section: Section) =>
    navigate({
      section,
      caseId: section === "Summary Explorer" ? lastCase.current : null,
    });

  const live = panel?.mode === "live";

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="border-b border-slate-200 bg-white">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-6 py-3">
          <h1 className="text-lg font-bold tracking-tight text-slate-900">GenAI Eval Harness</h1>
          {panel && (
            <span className="text-xs text-slate-500">
              {live ? "🟢 live" : "🟡 stub"} · {panel.panel.join(", ")}
            </span>
          )}
          {panel && !live && (
            <span className="text-xs text-slate-400">
              Stub mode: deterministic placeholder scores. Set JURY_MODE=live (+ API keys) for real
              judgments.
            </span>
          )}
        </div>
        <nav className="flex gap-1 px-4">
          {SECTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => openSection(s)}
              className={`-mb-px border-b-2 px-3 py-2 text-sm font-medium ${
                route.section === s
                  ? "border-indigo-600 text-indigo-700"
                  : "border-transparent text-slate-500 hover:border-slate-300 hover:text-slate-700"
              }`}
            >
              {s}
            </button>
          ))}
        </nav>
      </header>

      <main className="px-4 py-5">
        {route.section === "Overview" && <Overview openCase={openCase} />}
        {route.section === "Summary Explorer" && (
          <Explorer selectedCase={route.caseId} setSelectedCase={setSelectedCase} />
        )}
        {route.section === "Jury Config" && <JuryConfig onPanelChanged={refreshPanel} />}
        {route.section === "Live Judge" && <LiveJudge openCase={openCase} />}
        {route.section === "Calibrate" && <Calibrate />}
      </main>
    </div>
  );
}
