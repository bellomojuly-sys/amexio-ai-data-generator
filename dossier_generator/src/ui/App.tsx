import { useEffect, useState } from "react";
import { IS_HOSTED } from "../ai/settings";
import { ModelSettingsDialog } from "./components/ModelSettings";
import type { StepId } from "./useGenerator";
import { useGenerator } from "./useGenerator";
import { ConfigureStep } from "./steps/ConfigureStep";
import { PersonasStep } from "./steps/PersonasStep";
import { StorylinesStep } from "./steps/StorylinesStep";
import { DocumentsStep } from "./steps/DocumentsStep";
import { ValidateStep } from "./steps/ValidateStep";
import { ExportStep } from "./steps/ExportStep";

interface StepDef {
  id: StepId;
  title: string;
  hint: string;
}

const STEPS: StepDef[] = [
  { id: "configure", title: "Configure", hint: "Company, period, document types" },
  { id: "personas", title: "Personas", hint: "The AI proposes employees" },
  { id: "storylines", title: "Storylines", hint: "The AI writes each career" },
  { id: "documents", title: "Documents", hint: "Code builds PDFs and metadata" },
  { id: "validate", title: "Validate", hint: "Checks across all documents" },
  { id: "export", title: "Export", hint: "ZIP for Object Importer" },
];

export function App() {
  const gen = useGenerator();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 3500);
    return () => clearTimeout(t);
  }, [toast]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [gen.step]);

  const available: Record<StepId, boolean> = {
    configure: true,
    personas: true,
    storylines: !!gen.employees,
    documents: !!gen.set,
    validate: !!gen.set,
    export: !!gen.set,
  };
  const done: Record<StepId, boolean> = {
    configure: !!gen.employees,
    personas: !!gen.employees,
    storylines: !!gen.storylines,
    documents: !!gen.pkg,
    validate: !!gen.report && gen.report.errors === 0,
    export: false,
  };

  const modelLabel = gen.forcedOffline ? "No AI (this preset)" : gen.provider.label;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true" />
          <div style={{ minWidth: 0 }}>
            <div className="brand-name">Dossier Generator</div>
            <div className="brand-sub">Demo for AMEXIO · synthetic HR dossiers for OpenText Content Server</div>
          </div>
        </div>
        <div className="topbar-right">
          <span className="synthetic-pill" title="Every document carries AMEXIO's MOCK DATA banner">Synthetic data</span>
          <button className="model-chip" id="model-chip" onClick={() => setSettingsOpen(true)} title="Model settings">
            <span className={`dot ${gen.provider.id === "offline" ? "off" : ""}`} aria-hidden="true" />
            <span className="label">{modelLabel}</span>
          </button>
        </div>
      </header>

      <div className="body">
        <nav className="rail" aria-label="Steps">
          {STEPS.map((s, i) => (
            <button
              key={s.id}
              id={`step-${s.id}`}
              className={`rail-step ${done[s.id] && gen.step !== s.id ? "done" : ""}`}
              aria-current={gen.step === s.id ? "step" : undefined}
              disabled={!available[s.id]}
              onClick={() => gen.setStep(s.id)}
            >
              <span className="rail-num">{done[s.id] && gen.step !== s.id ? "✓" : i + 1}</span>
              <span>
                <span className="rail-title">{s.title}</span>
                <span className="rail-hint" style={{ display: "block" }}>{s.hint}</span>
              </span>
            </button>
          ))}
          <div className="rail-foot">
            {IS_HOSTED ? "Hosted demo. AI steps run on your own Claude account." : "Local version. Pick any model in Model settings."}
          </div>
        </nav>

        <main className="main">
          <div className="main-inner">
            {gen.step === "configure" && <ConfigureStep gen={gen} openSettings={() => setSettingsOpen(true)} />}
            {gen.step === "personas" && <PersonasStep gen={gen} openSettings={() => setSettingsOpen(true)} />}
            {gen.step === "storylines" && <StorylinesStep gen={gen} openSettings={() => setSettingsOpen(true)} />}
            {gen.step === "documents" && <DocumentsStep gen={gen} notify={setToast} />}
            {gen.step === "validate" && <ValidateStep gen={gen} />}
            {gen.step === "export" && <ExportStep gen={gen} notify={setToast} />}
          </div>
        </main>
      </div>

      {settingsOpen && (
        <ModelSettingsDialog
          settings={gen.settings}
          forcedOffline={gen.forcedOffline}
          onClose={() => setSettingsOpen(false)}
          onSave={(s) => {
            gen.setSettings(s);
            setSettingsOpen(false);
            setToast("Model settings saved");
          }}
        />
      )}
      {toast && (
        <div className="toast" role="status">
          {toast}
        </div>
      )}
    </div>
  );
}
