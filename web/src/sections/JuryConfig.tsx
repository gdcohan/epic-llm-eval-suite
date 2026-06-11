import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { DimensionConfig, JuryConfigData, ModelConfig, PanelInfo, PersonaConfig } from "../types";
import {
  Alert,
  Expander,
  Spinner,
  buttonClass,
  inputClass,
  primaryButtonClass,
  textareaClass,
} from "../components/ui";

type Notice = { kind: "error" | "success"; text: string } | null;

let nextId = 0;
const withIds = <T,>(items: T[]) => items.map((it) => ({ ...it, _id: `cfg-${nextId++}` }));

type EditableDim = DimensionConfig & { _id: string };
type EditablePersona = PersonaConfig & { _id: string };
// models are edited as a raw "provider:model" spec per row
type EditableModel = { _id: string; spec: string; enabled: boolean };

const toModelRows = (models: ModelConfig[]): EditableModel[] =>
  models.map((m) => ({
    _id: `cfg-${nextId++}`,
    spec: m.model ? `${m.provider}:${m.model}` : m.provider,
    enabled: m.enabled ?? true,
  }));

const parseModelRows = (rows: EditableModel[]): ModelConfig[] =>
  rows
    .map((r) => ({ spec: r.spec.trim(), enabled: r.enabled }))
    .filter((r) => r.spec)
    .map((r) => {
      const parts = r.spec.split(":").map((x) => x.trim());
      return { provider: parts[0], model: parts[1] ?? "", enabled: r.enabled };
    });

function SectionShell({
  title,
  caption,
  children,
}: {
  title: string;
  caption?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-base font-semibold text-slate-800">{title}</h3>
      {caption && <p className="mb-3 mt-1 text-xs text-slate-500">{caption}</p>}
      {children}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block text-xs font-medium text-slate-600">
      {label}
      <div className="mt-1">{children}</div>
    </label>
  );
}

export default function JuryConfig({ onPanelChanged }: { onPanelChanged?: () => void }) {
  const [cfg, setCfg] = useState<JuryConfigData | null>(null);
  const [dims, setDims] = useState<EditableDim[]>([]);
  const [personas, setPersonas] = useState<EditablePersona[]>([]);
  const [models, setModels] = useState<EditableModel[]>([]);
  const [guidance, setGuidance] = useState("");
  const [contract, setContract] = useState("");
  const [panel, setPanel] = useState<PanelInfo | null>(null);
  const [notice, setNotice] = useState<Notice>(null);

  // prompt preview
  const [previewDim, setPreviewDim] = useState("");
  const [previewPersona, setPreviewPersona] = useState("");
  const [previewText, setPreviewText] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    const [c, p] = await Promise.all([api.get("/api/config"), api.get("/api/panel")]);
    setCfg(c);
    setDims(withIds(c.dimensions));
    // older configs may predate the persona enabled flag — default it on
    setPersonas(withIds(c.personas.map((p: PersonaConfig) => ({ ...p, enabled: p.enabled ?? true }))));
    setModels(toModelRows(c.models));
    setGuidance(c.source_guidance);
    setContract(c.output_contract);
    setPanel(p);
  }, []);

  useEffect(() => {
    loadAll().catch((e) => setNotice({ kind: "error", text: String(e) }));
  }, [loadAll]);

  const act = async (fn: () => Promise<unknown>, successText: string) => {
    try {
      await fn();
      setPanel(await api.get("/api/panel"));
      onPanelChanged?.(); // keep the app header's juror list in sync
      setNotice({ kind: "success", text: successText });
    } catch (e) {
      setNotice({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  };

  const showPrompt = async () => {
    if (!previewDim) return;
    try {
      const params = new URLSearchParams({ dimension: previewDim });
      if (previewPersona) params.set("persona", previewPersona);
      const res = await api.get(`/api/config/prompt-preview?${params}`);
      setPreviewText(res.system);
    } catch (e) {
      setNotice({ kind: "error", text: e instanceof Error ? e.message : String(e) });
    }
  };

  if (!cfg) return <Spinner label="loading config…" />;

  const updateDim = (id: string, patch: Partial<DimensionConfig>) =>
    setDims((ds) => ds.map((d) => (d._id === id ? { ...d, ...patch } : d)));
  const updatePersona = (id: string, patch: Partial<PersonaConfig>) =>
    setPersonas((ps) => ps.map((p) => (p._id === id ? { ...p, ...patch } : p)));

  return (
    <div className="max-w-5xl space-y-5">
      {notice && <Alert kind={notice.kind}>{notice.text}</Alert>}

      <SectionShell
        title="Dimensions"
        caption="Each dimension is one juror prompt. Toggle, edit, add, or remove — applies to the next run."
      >
        <div className="space-y-2">
          {dims.map((d) => (
            <Expander
              key={d._id}
              title={`${d.name || "new dimension"}${d.enabled ? "" : "  ·  (disabled)"}`}
              defaultOpen={!d.name}
            >
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
                  <input
                    type="checkbox"
                    checked={d.enabled}
                    onChange={(e) => updateDim(d._id, { enabled: e.target.checked })}
                  />
                  enabled
                </label>
                <Field label="name">
                  <input className={inputClass} value={d.name} onChange={(e) => updateDim(d._id, { name: e.target.value })} />
                </Field>
                <Field label="description">
                  <input
                    className={inputClass}
                    value={d.description}
                    onChange={(e) => updateDim(d._id, { description: e.target.value })}
                  />
                </Field>
                <Field label="scale">
                  <input className={`${inputClass} !w-28`} value={d.scale} onChange={(e) => updateDim(d._id, { scale: e.target.value })} />
                </Field>
                <Field label="prompt">
                  <textarea
                    className={textareaClass}
                    rows={8}
                    value={d.prompt}
                    onChange={(e) => updateDim(d._id, { prompt: e.target.value })}
                  />
                </Field>
                <button
                  type="button"
                  className={`${buttonClass} !text-xs text-red-600`}
                  onClick={() => setDims((ds) => ds.filter((x) => x._id !== d._id))}
                >
                  remove
                </button>
              </div>
            </Expander>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            className={buttonClass}
            onClick={() =>
              setDims((ds) => [
                ...ds,
                { _id: `cfg-${nextId++}`, name: "", description: "", prompt: "", scale: "1-5", enabled: true },
              ])
            }
          >
            ➕ add dimension
          </button>
          <button
            type="button"
            className={primaryButtonClass}
            onClick={() =>
              act(async () => {
                const res = await api.put("/api/config/dimensions", dims.map(({ _id, ...d }) => d));
                setNotice({ kind: "success", text: `Saved — ${res.active} active dimension(s).` });
              }, "Saved dimensions.")
            }
          >
            💾 save dimensions
          </button>
          <button
            type="button"
            className={buttonClass}
            onClick={() =>
              act(async () => {
                const fresh = await api.del("/api/config/dimensions");
                setDims(withIds(fresh));
              }, "Reset dimensions to defaults.")
            }
          >
            ↺ reset dimensions
          </button>
        </div>
      </SectionShell>

      <SectionShell
        title="Personas"
        caption="Reviewer styles. The live jury = models × personas (one juror per pairing)."
      >
        <div className="space-y-2">
          {personas.map((p) => (
            <Expander
              key={p._id}
              title={`${p.name || "new persona"}  ·  temp ${p.temperature}${p.enabled ? "" : "  ·  (disabled)"}`}
              defaultOpen={!p.name}
            >
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-xs font-medium text-slate-600">
                  <input
                    type="checkbox"
                    checked={p.enabled}
                    onChange={(e) => updatePersona(p._id, { enabled: e.target.checked })}
                  />
                  enabled
                </label>
                <Field label="name">
                  <input className={inputClass} value={p.name} onChange={(e) => updatePersona(p._id, { name: e.target.value })} />
                </Field>
                <Field label="temperature">
                  <input
                    type="number"
                    min={0}
                    max={2}
                    step={0.1}
                    className={`${inputClass} !w-28`}
                    value={p.temperature}
                    onChange={(e) => updatePersona(p._id, { temperature: Number(e.target.value) })}
                  />
                </Field>
                <Field label="persona text (prepended to the prompt)">
                  <textarea
                    className={textareaClass}
                    rows={3}
                    value={p.text}
                    onChange={(e) => updatePersona(p._id, { text: e.target.value })}
                  />
                </Field>
                <button
                  type="button"
                  className={`${buttonClass} !text-xs text-red-600`}
                  onClick={() => setPersonas((ps) => ps.filter((x) => x._id !== p._id))}
                >
                  remove
                </button>
              </div>
            </Expander>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            className={buttonClass}
            onClick={() =>
              setPersonas((ps) => [
                ...ps,
                { _id: `cfg-${nextId++}`, name: "", temperature: 0.2, text: "", enabled: true },
              ])
            }
          >
            ➕ add persona
          </button>
          <button
            type="button"
            className={primaryButtonClass}
            onClick={() =>
              act(async () => {
                await api.put("/api/config/personas", personas.map(({ _id, ...p }) => p));
              }, "Saved personas.")
            }
          >
            💾 save personas
          </button>
          <button
            type="button"
            className={buttonClass}
            onClick={() =>
              act(async () => {
                const fresh = await api.del("/api/config/personas");
                setPersonas(withIds(fresh));
              }, "Reset personas to defaults.")
            }
          >
            ↺ reset personas
          </button>
        </div>
      </SectionShell>

      <SectionShell
        title="Models"
        caption="provider:model (providers: anthropic, openai, gemini). Live mode only. Disabled models stay configured but are skipped when the panel is assembled."
      >
        <div className="space-y-2">
          {models.map((m) => (
            <div key={m._id} className="flex items-center gap-2">
              <label className="flex items-center gap-1.5 text-xs font-medium text-slate-600" title="enabled">
                <input
                  type="checkbox"
                  checked={m.enabled}
                  onChange={(e) =>
                    setModels((ms) => ms.map((x) => (x._id === m._id ? { ...x, enabled: e.target.checked } : x)))
                  }
                />
              </label>
              <input
                className={`${inputClass} !w-96 font-mono !text-[13px] ${m.enabled ? "" : "opacity-50"}`}
                placeholder="provider:model"
                value={m.spec}
                onChange={(e) =>
                  setModels((ms) => ms.map((x) => (x._id === m._id ? { ...x, spec: e.target.value } : x)))
                }
              />
              {!m.enabled && <span className="text-xs text-slate-400">(disabled)</span>}
              <button
                type="button"
                className={`${buttonClass} !px-2 !py-1 !text-xs text-red-600`}
                onClick={() => setModels((ms) => ms.filter((x) => x._id !== m._id))}
              >
                remove
              </button>
            </div>
          ))}
        </div>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            className={buttonClass}
            onClick={() => setModels((ms) => [...ms, { _id: `cfg-${nextId++}`, spec: "", enabled: true }])}
          >
            ➕ add model
          </button>
          <button
            type="button"
            className={primaryButtonClass}
            onClick={() =>
              act(async () => {
                await api.put("/api/config/models", parseModelRows(models));
              }, "Saved models.")
            }
          >
            💾 save models
          </button>
          <button
            type="button"
            className={buttonClass}
            onClick={() =>
              act(async () => {
                const fresh: ModelConfig[] = await api.del("/api/config/models");
                setModels(toModelRows(fresh));
              }, "Reset models to defaults.")
            }
          >
            ↺ reset models
          </button>
        </div>
      </SectionShell>

      <SectionShell
        title="Reconciliation guidance (shared)"
        caption="How jurors should reconcile notes that conflict (temporal, status/certainty, authority, specificity, repeated measures, clear error) before scoring."
      >
        <textarea className={textareaClass} rows={12} value={guidance} onChange={(e) => setGuidance(e.target.value)} />
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            className={primaryButtonClass}
            onClick={() => act(() => api.put("/api/config/source-guidance", { text: guidance }), "Saved guidance.")}
          >
            💾 save
          </button>
          <button
            type="button"
            className={buttonClass}
            onClick={() =>
              act(async () => {
                const res = await api.del("/api/config/source-guidance");
                setGuidance(res.text);
              }, "Reset guidance to default.")
            }
          >
            ↺ reset
          </button>
        </div>
      </SectionShell>

      <SectionShell
        title="Output contract (shared)"
        caption="⚠️ Load-bearing: the app parses score / synopsis / findings and uses the verbatim quotes for source-links. Keep those keys or scores/links break. Use {scale} as the score-range placeholder."
      >
        <textarea className={textareaClass} rows={10} value={contract} onChange={(e) => setContract(e.target.value)} />
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            className={primaryButtonClass}
            onClick={() => act(() => api.put("/api/config/output-contract", { text: contract }), "Saved contract.")}
          >
            💾 save
          </button>
          <button
            type="button"
            className={buttonClass}
            onClick={() =>
              act(async () => {
                const res = await api.del("/api/config/output-contract");
                setContract(res.text);
              }, "Reset contract to default.")
            }
          >
            ↺ reset
          </button>
        </div>
      </SectionShell>

      <SectionShell title="Panel preview">
        {panel && (
          <div className="space-y-1 text-sm text-slate-600">
            <div>
              {panel.mode === "live" ? "🟢 live" : "🟡 stub"} · {panel.panel.length} juror(s):{" "}
              {panel.panel.join(", ")}
            </div>
            <div>
              Calls per case ≈ jurors × dimensions = {panel.panel.length} × {panel.n_dimensions} ={" "}
              <b>{panel.calls_per_case}</b>
            </div>
          </div>
        )}
      </SectionShell>

      <SectionShell title="Show the prompt" caption="Reflects the SAVED config (save your edits above to preview them).">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="dimension">
            <select className={`${inputClass} !w-56`} value={previewDim} onChange={(e) => setPreviewDim(e.target.value)}>
              <option value="">— pick —</option>
              {dims
                .filter((d) => d.enabled && d.name)
                .map((d) => (
                  <option key={d._id} value={d.name}>
                    {d.name}
                  </option>
                ))}
            </select>
          </Field>
          <Field label="persona">
            <select
              className={`${inputClass} !w-56`}
              value={previewPersona}
              onChange={(e) => setPreviewPersona(e.target.value)}
            >
              <option value="">(none)</option>
              {personas
                .filter((p) => p.name)
                .map((p) => (
                  <option key={p._id} value={p.name}>
                    {p.name}
                  </option>
                ))}
            </select>
          </Field>
          <button type="button" className={buttonClass} disabled={!previewDim} onClick={showPrompt}>
            show
          </button>
        </div>
        {previewText && (
          <>
            <div className="mt-3 text-xs text-slate-500">
              Exactly what this juror gets as the system prompt (notes + summary are the user message):
            </div>
            <pre className="mt-1 max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-900 p-3 text-[11px] leading-relaxed text-slate-100">
              {previewText}
            </pre>
          </>
        )}
      </SectionShell>
    </div>
  );
}
