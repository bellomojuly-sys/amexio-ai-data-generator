import { useEffect, useState } from "react";
import { createProvider, getSample } from "../../ai/providers";
import { IS_HOSTED } from "../../ai/settings";
import type { ModelSettings, ProviderId } from "../../ai/types";
import { ModelError, OPENAI_PRESETS } from "../../ai/types";

interface Props {
  settings: ModelSettings;
  forcedOffline: boolean;
  onClose(): void;
  onSave(s: ModelSettings): void;
}

const PROVIDERS: { id: ProviderId; name: string; desc: string }[] = [
  { id: "claude", name: "Claude (your Claude account)", desc: "Only in the hosted Claude page. Runs on the Claude account of whoever uses the page. No key needed." },
  { id: "anthropic", name: "Anthropic API", desc: "Your own API key. Local version only." },
  { id: "openai", name: "OpenAI-compatible", desc: "OpenAI, Gemini, Groq, OpenRouter, or a free local model (Ollama, LM Studio). Local version only." },
  { id: "offline", name: "No AI", desc: "Built-in sample generator. Free, instant, reproducible. Good for tests and large volumes." },
];

export function ModelSettingsDialog({ settings, forcedOffline, onClose, onSave }: Props) {
  const [draft, setDraft] = useState<ModelSettings>(() => JSON.parse(JSON.stringify(settings)));
  const [claudeAvailable, setClaudeAvailable] = useState<boolean | null>(null);
  const [test, setTest] = useState<{ state: "idle" | "running" | "ok" | "fail"; message?: string }>({ state: "idle" });

  useEffect(() => {
    let alive = true;
    getSample().then((s) => alive && setClaudeAvailable(!!s));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const disabledReason = (id: ProviderId): string | null => {
    if (id === "claude" && claudeAvailable === false) return "Not available here: open the hosted Claude page to use it.";
    if ((id === "anthropic" || id === "openai") && IS_HOSTED) return "Not available in the hosted page, which cannot connect to other services. Run the local version.";
    return null;
  };

  const preset = OPENAI_PRESETS.find((p) => p.id === draft.openai.preset) ?? OPENAI_PRESETS[OPENAI_PRESETS.length - 1];

  async function runTest() {
    setTest({ state: "running" });
    try {
      const provider = createProvider(draft);
      const text = await provider.complete({
        system: "Reply with JSON only.",
        prompt: 'Reply with exactly this JSON: {"ok":true}',
        maxTokens: 50,
      });
      setTest(text.includes("ok") ? { state: "ok", message: `Connected: ${provider.describe()}` } : { state: "fail", message: `Unexpected answer: ${text.slice(0, 120)}` });
    } catch (e) {
      setTest({ state: "fail", message: e instanceof ModelError ? e.message : String((e as Error)?.message ?? e) });
    }
  }

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="model-title">
        <div className="dialog-head">
          <h2 id="model-title" style={{ fontSize: 18 }}>Model settings</h2>
          <button className="btn btn-sm" onClick={onClose}>Close</button>
        </div>
        <div className="dialog-body">
          {forcedOffline && (
            <div className="callout warn">The selected preset uses the sample generator (no AI). Choosing a model here switches the run to that model; the AMEXIO example always uses its fixed data.</div>
          )}
          <p className="muted small">
            The model only proposes people and careers. Code assigns IDs, checks every value, computes amounts and writes the PDFs and import.xml, so any model can be swapped in.
          </p>
          <div className="provider-grid">
            {PROVIDERS.map((p) => {
              const reason = disabledReason(p.id);
              return (
                <button
                  key={p.id}
                  id={`provider-${p.id}`}
                  className="provider"
                  aria-pressed={draft.provider === p.id}
                  disabled={!!reason}
                  onClick={() => {
                    setDraft({ ...draft, provider: p.id });
                    setTest({ state: "idle" });
                  }}
                >
                  <span className="name">{p.name}</span>
                  <span className="desc">{reason ?? p.desc}</span>
                </button>
              );
            })}
          </div>

          {draft.provider === "claude" && (
            <div className="stack">
              <div className="field">
                <span className="label">Model tier</span>
                <div className="seg" role="group" aria-label="Model tier">
                  {(["quick", "default", "complex"] as const).map((t) => (
                    <button key={t} aria-pressed={draft.claude.tier === t} onClick={() => setDraft({ ...draft, claude: { tier: t } })}>
                      {t === "quick" ? "Fast" : t === "default" ? "Balanced" : "Most capable"}
                    </button>
                  ))}
                </div>
                <span className="help">Every generation uses the Claude account of the person using this page, so it counts against their own limits. The first request asks them to allow it.</span>
              </div>
            </div>
          )}

          {draft.provider === "anthropic" && (
            <div className="grid-2">
              <div className="field">
                <label htmlFor="anthropic-key">API key</label>
                <input id="anthropic-key" className="input" type="password" autoComplete="off" value={draft.anthropic.apiKey} placeholder="sk-ant-..." onChange={(e) => setDraft({ ...draft, anthropic: { ...draft.anthropic, apiKey: e.target.value } })} />
              </div>
              <div className="field">
                <label htmlFor="anthropic-model">Model</label>
                <input id="anthropic-model" className="input" value={draft.anthropic.model} onChange={(e) => setDraft({ ...draft, anthropic: { ...draft.anthropic, model: e.target.value } })} />
                <span className="help">For example claude-sonnet-5-5 or claude-haiku-5-5.</span>
              </div>
            </div>
          )}

          {draft.provider === "openai" && (
            <div className="stack">
              <div className="field">
                <label htmlFor="openai-preset">Service</label>
                <select
                  id="openai-preset"
                  className="select"
                  value={draft.openai.preset}
                  onChange={(e) => {
                    const p = OPENAI_PRESETS.find((x) => x.id === e.target.value)!;
                    setDraft({ ...draft, openai: { ...draft.openai, preset: p.id, baseUrl: p.baseUrl || draft.openai.baseUrl, model: p.modelHint && !p.modelHint.includes(" ") ? p.modelHint : draft.openai.model } });
                  }}
                >
                  {OPENAI_PRESETS.map((p) => (
                    <option key={p.id} value={p.id}>{p.label}</option>
                  ))}
                </select>
                <span className="help">{preset.note}</span>
              </div>
              <div className="grid-2">
                <div className="field">
                  <label htmlFor="openai-url">Address</label>
                  <input id="openai-url" className="input mono" value={draft.openai.baseUrl} placeholder="https://.../v1" onChange={(e) => setDraft({ ...draft, openai: { ...draft.openai, baseUrl: e.target.value } })} />
                </div>
                <div className="field">
                  <label htmlFor="openai-model">Model</label>
                  <input id="openai-model" className="input" value={draft.openai.model} placeholder={preset.modelHint} onChange={(e) => setDraft({ ...draft, openai: { ...draft.openai, model: e.target.value } })} />
                </div>
              </div>
              <div className="field">
                <label htmlFor="openai-key">API key {preset.needsKey ? "" : "(not needed for local models)"}</label>
                <input id="openai-key" className="input" type="password" autoComplete="off" value={draft.openai.apiKey} onChange={(e) => setDraft({ ...draft, openai: { ...draft.openai, apiKey: e.target.value } })} />
              </div>
            </div>
          )}

          {(draft.provider === "anthropic" || draft.provider === "openai") && (
            <label className="check">
              <input type="checkbox" checked={draft.rememberKeys} onChange={(e) => setDraft({ ...draft, rememberKeys: e.target.checked })} />
              <span>
                Remember the key in this browser
                <span className="help" style={{ display: "block" }}>Off: the key is forgotten when you close the page. Keys are never part of exports or the hosted page.</span>
              </span>
            </label>
          )}

          {draft.provider !== "offline" && (
            <div className="row">
              <button className="btn" onClick={runTest} disabled={test.state === "running" || !!disabledReason(draft.provider)}>
                {test.state === "running" ? "Testing..." : "Test connection"}
              </button>
              {test.state === "ok" && <span className="badge badge-ok">{test.message}</span>}
              {test.state === "fail" && <span className="small" style={{ color: "var(--err)" }}>{test.message}</span>}
            </div>
          )}

          <div className="row" style={{ justifyContent: "flex-end" }}>
            <button className="btn" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" id="save-model" onClick={() => onSave(draft)}>Use this model</button>
          </div>
        </div>
      </div>
    </div>
  );
}
