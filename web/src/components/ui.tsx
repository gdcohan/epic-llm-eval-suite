import { useEffect, useRef, useState, type ReactNode } from "react";
import { scoreColor, COLORS, HARM_COLORS, AGREEMENT_LABELS, fmtScore } from "../lib";
import type { Finding } from "../types";

export function Badge({ color, children }: { color: string; children: ReactNode }) {
  return (
    <span
      className="inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium text-white"
      style={{ background: color }}
    >
      {children}
    </span>
  );
}

export function ScoreBadge({
  score,
  scale = "1-5",
}: {
  score: number | null | undefined;
  scale?: string;
}) {
  const max = Number(scale.split("-").pop()) || 5;
  return (
    <Badge color={scoreColor(score, max)}>
      {fmtScore(score)} / {max}
    </Badge>
  );
}

export function AgreementBadge({ agreement }: { agreement: string | null | undefined }) {
  if (!agreement) return null;
  return <span className="text-xs text-slate-500">{AGREEMENT_LABELS[agreement] ?? agreement}</span>;
}

export function HarmBadge({
  finding,
}: {
  finding: Pick<Finding, "harm_severity" | "harm_category">;
}) {
  const sev = (finding.harm_severity || "").trim().toLowerCase();
  if (!sev) return null;
  const label = finding.harm_category ? `${sev} · ${finding.harm_category}` : sev;
  return <Badge color={HARM_COLORS[sev] ?? COLORS.muted}>{label}</Badge>;
}

/** Merge-highlight verbatim quotes inside text (mirrors the Streamlit _highlight). */
function highlightRanges(text: string, quotes: (string | null | undefined)[]): [number, number][] {
  const ranges: [number, number][] = [];
  for (const q of quotes) {
    const quote = (q || "").trim();
    if (!quote) continue;
    let idx = text.indexOf(quote);
    while (idx !== -1) {
      ranges.push([idx, idx + quote.length]);
      idx = text.indexOf(quote, idx + quote.length);
    }
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([r[0], r[1]]);
  }
  return merged;
}

export function HighlightText({
  text,
  quotes = [],
}: {
  text: string;
  quotes?: (string | null | undefined)[];
}) {
  const body = text || "(empty)";
  const ranges = highlightRanges(body, quotes);
  const nodes: ReactNode[] = [];
  let pos = 0;
  ranges.forEach(([s, e], i) => {
    if (s > pos) nodes.push(body.slice(pos, s));
    nodes.push(
      <mark key={i} className="rounded-sm bg-yellow-200 px-0.5">
        {body.slice(s, e)}
      </mark>,
    );
    pos = e;
  });
  if (pos < body.length) nodes.push(body.slice(pos));
  return (
    <div className="whitespace-pre-wrap font-mono text-[13px] leading-relaxed text-slate-800">
      {nodes}
    </div>
  );
}

export function Expander({
  title,
  children,
  open,
  defaultOpen = false,
  scrollIntoViewWhenOpened = false,
}: {
  title: ReactNode;
  children: ReactNode;
  open?: boolean; // when provided, (re)apply it on change but still allow manual toggling
  defaultOpen?: boolean;
  scrollIntoViewWhenOpened?: boolean;
}) {
  const [isOpen, setIsOpen] = useState(open ?? defaultOpen);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (open === undefined) return;
    setIsOpen(open);
    if (open && scrollIntoViewWhenOpened) {
      setTimeout(() => ref.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
    }
  }, [open, scrollIntoViewWhenOpened]);
  return (
    <div ref={ref} className="rounded-lg border border-slate-200 bg-white">
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        <span className="text-slate-400">{isOpen ? "▾" : "▸"}</span>
        <span className="min-w-0 flex-1 truncate">{title}</span>
      </button>
      {isOpen && <div className="border-t border-slate-100 px-3 py-3">{children}</div>}
    </div>
  );
}

export function KpiCard({
  label,
  value,
  onClick,
  hint = "open »",
}: {
  label: string;
  value: ReactNode;
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void;
  hint?: string;
}) {
  const clickable = Boolean(onClick);
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!clickable}
      className={`rounded-xl border border-slate-200 bg-white p-4 text-left shadow-sm ${
        clickable ? "cursor-pointer hover:border-indigo-300" : "cursor-default"
      }`}
    >
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900">{value}</div>
      {clickable && <div className="mt-1 text-xs text-indigo-600">{hint}</div>}
    </button>
  );
}

export function BarChart({
  title,
  data,
  max,
  color = "#6366f1",
}: {
  title: string;
  data: Record<string, number>;
  max?: number;
  color?: string;
}) {
  const entries = Object.entries(data);
  const top = max ?? Math.max(1, ...entries.map(([, v]) => v));
  return (
    <div className="flex h-full flex-col rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 text-sm font-medium text-slate-600">{title}</div>
      {entries.length === 0 && <div className="text-sm text-slate-400">no data</div>}
      <div className="flex flex-1 flex-col justify-around gap-2">
        {entries.map(([label, value]) => (
          <div key={label} className="flex items-center gap-3 text-sm">
            <div className="w-36 shrink-0 truncate text-slate-600">{label}</div>
            <div className="h-4 flex-1 overflow-hidden rounded bg-slate-100">
              <div
                className="h-full rounded"
                style={{ width: `${Math.min(100, (value / top) * 100)}%`, background: color }}
              />
            </div>
            <div className="w-12 shrink-0 text-right font-medium text-slate-700">{fmtScore(value)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-slate-500">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-500" />
      {label}
    </span>
  );
}

export function Alert({ kind, children }: { kind: "error" | "info" | "success" | "warning"; children: ReactNode }) {
  const styles = {
    error: "border-red-200 bg-red-50 text-red-800",
    info: "border-sky-200 bg-sky-50 text-sky-800",
    success: "border-green-200 bg-green-50 text-green-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
  }[kind];
  return <div className={`rounded-lg border px-3 py-2 text-sm ${styles}`}>{children}</div>;
}

export const inputClass =
  "w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-800 " +
  "placeholder:text-slate-400 focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100";

export const textareaClass = `${inputClass} font-mono text-[13px] leading-relaxed`;

export const buttonClass =
  "inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm " +
  "font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";

export const primaryButtonClass =
  "inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white " +
  "hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50";
