import { useCallback, useMemo, useRef, useState } from "react";
import { createProvider } from "../ai/providers";
import { loadSettings, saveSettings } from "../ai/settings";
import type { ModelSettings } from "../ai/types";
import { ModelError } from "../ai/types";
import { cloneConfig, DEFAULT_CONFIG, LIMITS, newGenerationId } from "../generate/config";
import { examplePreset } from "../generate/examplePreset";
import { expandDossiers } from "../generate/expand";
import type { ModelExchange } from "../generate/pipeline";
import { runPersonaStep, runStorylineStep } from "../generate/pipeline";
import type { DossierPackage, DossierSet, GenerationConfig } from "../generate/types";
import type { Correction, Employee, Storyline } from "../model/dossier";
import { buildImportXml } from "../export/importXml";
import { BREAKERS } from "../validate/breakers";
import type { ValidationReport } from "../validate/validate";
import { validate } from "../validate/validate";
import { DOC_TYPES } from "../spec/doctypes";

export type StepId = "configure" | "personas" | "storylines" | "documents" | "validate" | "export";
export type PresetId = "example" | "small" | "volume" | "custom";

export interface RunState {
  status: "idle" | "running" | "done" | "error";
  label?: string;
  stream?: string;
  error?: string;
  errorKind?: ModelError["kind"];
  progress?: [number, number];
  startedAt?: number;
}

export interface PresetDef {
  id: PresetId;
  title: string;
  summary: string;
  meta: string;
  config: () => GenerationConfig;
  /** Runs without a model, whatever is selected. */
  offline: boolean;
}

export const PRESETS: PresetDef[] = [
  {
    id: "example",
    title: "AMEXIO example",
    summary: "The 4 employees and 20 documents from AMEXIO's mock package, rebuilt from the generator's own rules.",
    meta: "4 employees · 5 document types · no AI",
    config: () => examplePreset().config,
    offline: true,
  },
  {
    id: "small",
    title: "Small company",
    summary: "Ten employees with three years of history. The AI writes the people and their careers.",
    meta: "10 employees · 9 document types · uses the model",
    config: () => cloneConfig(DEFAULT_CONFIG),
    offline: false,
  },
  {
    id: "volume",
    title: "Volume test",
    summary: "Sixty employees with eight years of history, made by the sample generator to test scale.",
    meta: "60 employees · ~5,000 documents · no AI",
    config: () => {
      const c = cloneConfig(DEFAULT_CONFIG);
      c.employeeCount = 60;
      c.historyYears = 8;
      c.departments = ["IT", "Human Resources", "Logistics", "Finance", "Customer Service"];
      c.earliestHire = "2012-01-01";
      return c;
    },
    offline: true,
  },
];

export interface AppliedBreaker {
  id: string;
  note: string;
}

export function useGenerator() {
  const [settings, setSettingsState] = useState<ModelSettings>(() => loadSettings());
  const [presetId, setPresetId] = useState<PresetId>("small");
  const [config, setConfigState] = useState<GenerationConfig>(() => cloneConfig(DEFAULT_CONFIG));
  const [step, setStep] = useState<StepId>("configure");
  const [generationId, setGenerationId] = useState<string>("");

  const [employees, setEmployees] = useState<Employee[] | null>(null);
  const [personaCorrections, setPersonaCorrections] = useState<Correction[]>([]);
  const [personaSource, setPersonaSource] = useState("");
  const [storylines, setStorylines] = useState<Record<string, Storyline> | null>(null);
  const [storyCorrections, setStoryCorrections] = useState<Correction[]>([]);
  const [storySource, setStorySource] = useState("");
  const [exchanges, setExchanges] = useState<ModelExchange[]>([]);
  const [breakers, setBreakers] = useState<AppliedBreaker[]>([]);
  const [personaRun, setPersonaRun] = useState<RunState>({ status: "idle" });
  const [storyRun, setStoryRun] = useState<RunState>({ status: "idle" });
  const abortRef = useRef<AbortController | null>(null);

  const [presetOffline, setPresetOffline] = useState(false);
  const forcedOffline = presetId === "example" || presetOffline;
  const provider = useMemo(() => createProvider(forcedOffline ? { ...settings, provider: "offline" } : settings), [settings, forcedOffline]);

  /** Choosing a model in Model settings overrides a preset's "no AI" choice. */
  const setSettings = useCallback((s: ModelSettings) => {
    setSettingsState(s);
    saveSettings(s);
    setPresetOffline(false);
  }, []);

  const resetGenerated = useCallback(() => {
    abortRef.current?.abort();
    setEmployees(null);
    setStorylines(null);
    setPersonaCorrections([]);
    setStoryCorrections([]);
    setExchanges([]);
    setBreakers([]);
    setPersonaRun({ status: "idle" });
    setStoryRun({ status: "idle" });
  }, []);

  const setConfig = useCallback(
    (c: GenerationConfig, keepPreset = false) => {
      setConfigState(c);
      if (!keepPreset) setPresetId("custom");
    },
    [],
  );

  const choosePreset = useCallback(
    (id: PresetId) => {
      const p = PRESETS.find((x) => x.id === id);
      if (!p) return;
      setPresetId(id);
      setPresetOffline(p.offline);
      setConfigState(p.config());
      resetGenerated();
    },
    [resetGenerated],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const generatePersonas = useCallback(async () => {
    abortRef.current?.abort();
    const ctl = new AbortController();
    abortRef.current = ctl;
    setStorylines(null);
    setStoryCorrections([]);
    setStoryRun({ status: "idle" });
    setBreakers([]);
    setPersonaRun({ status: "running", label: "Personas", stream: "", startedAt: Date.now() });
    try {
      if (presetId === "example") {
        const ex = examplePreset();
        setEmployees(ex.employees);
        setPersonaCorrections([]);
        setPersonaSource(ex.provenance.personas ?? "");
        setExchanges([]);
      } else {
        const result = await runPersonaStep(config, provider, {
          signal: ctl.signal,
          onText: (label, text) => setPersonaRun((r) => ({ ...r, label, stream: text })),
        });
        setEmployees(result.employees);
        setPersonaCorrections(result.corrections);
        setPersonaSource(result.source);
        setExchanges(result.exchanges);
      }
      setGenerationId(newGenerationId(config.seed));
      setPersonaRun((r) => ({ ...r, status: "done" }));
    } catch (e) {
      const err = e instanceof ModelError ? e : new ModelError((e as Error)?.message ?? "Something went wrong.", "retry");
      setPersonaRun((r) => ({ ...r, status: err.kind === "cancelled" ? "idle" : "error", error: err.message, errorKind: err.kind }));
    }
  }, [config, provider, presetId]);

  const generateStorylines = useCallback(async () => {
    if (!employees) return;
    abortRef.current?.abort();
    const ctl = new AbortController();
    abortRef.current = ctl;
    setBreakers([]);
    setStoryRun({ status: "running", label: "Storylines", stream: "", progress: [0, employees.length], startedAt: Date.now() });
    try {
      if (presetId === "example") {
        const ex = examplePreset();
        setStorylines(ex.storylines);
        setStoryCorrections([]);
        setStorySource(ex.provenance.storylines ?? "");
      } else {
        const result = await runStorylineStep(config, employees, provider, {
          signal: ctl.signal,
          onText: (label, text) => setStoryRun((r) => ({ ...r, label, stream: text })),
          onProgress: (done, total) => setStoryRun((r) => ({ ...r, progress: [done, total] })),
        });
        setStorylines(result.storylines);
        setStoryCorrections(result.corrections);
        setStorySource(result.source);
        setExchanges((x) => [...x.filter((e) => e.label === "Personas"), ...result.exchanges]);
      }
      setStoryRun((r) => ({ ...r, status: "done" }));
    } catch (e) {
      const err = e instanceof ModelError ? e : new ModelError((e as Error)?.message ?? "Something went wrong.", "retry");
      setStoryRun((r) => ({ ...r, status: err.kind === "cancelled" ? "idle" : "error", error: err.message, errorKind: err.kind }));
    }
  }, [config, employees, provider, presetId]);

  /** Editing a persona invalidates the storylines that were written for it. */
  const updateEmployee = useCallback((id: string, patch: Partial<Employee>) => {
    setEmployees((list) => (list ? list.map((e) => (e.id === id ? { ...e, ...patch } : e)) : list));
    setStorylines(null);
    setStoryRun({ status: "idle" });
    setBreakers([]);
  }, []);

  const updateStoryline = useCallback((employeeId: string, s: Storyline) => {
    setStorylines((all) => (all ? { ...all, [employeeId]: s } : all));
    setBreakers([]);
  }, []);

  const set: DossierSet | null = useMemo(() => {
    if (!employees || !storylines) return null;
    const ex = presetId === "example" ? examplePreset() : null;
    return {
      generationId: ex ? ex.generationId : generationId,
      config,
      employees,
      storylines,
      corrections: [...personaCorrections, ...storyCorrections],
      overrides: ex?.overrides ?? [],
      updates: ex?.updates,
      provenance: { personas: personaSource, storylines: storySource },
    };
  }, [employees, storylines, presetId, generationId, config, personaCorrections, storyCorrections, personaSource, storySource]);

  const pkg: DossierPackage | null = useMemo(() => {
    if (!set) return null;
    const p = expandDossiers(set);
    for (const b of breakers) BREAKERS.find((x) => x.id === b.id)?.apply(set, p);
    return p;
  }, [set, breakers]);

  const xml = useMemo(() => (set && pkg ? buildImportXml(set, pkg) : ""), [set, pkg]);

  const report: ValidationReport | null = useMemo(() => {
    if (!set || !pkg) return null;
    return validate(set, pkg, {
      xml,
      parseXml: (text) => {
        if (typeof DOMParser === "undefined") return null;
        const doc = new DOMParser().parseFromString(text, "application/xml");
        const err = doc.getElementsByTagName("parsererror")[0];
        return err ? (err.textContent ?? "parse error").slice(0, 200) : null;
      },
    });
  }, [set, pkg, xml]);

  const applyBreaker = useCallback(
    (id: string) => {
      if (!set) return;
      const probe = expandDossiers(set);
      for (const b of breakers) BREAKERS.find((x) => x.id === b.id)?.apply(set, probe);
      const note = BREAKERS.find((x) => x.id === id)?.apply(set, probe);
      if (note) setBreakers((list) => [...list, { id, note }]);
    },
    [set, breakers],
  );

  const enabledTypes = DOC_TYPES.filter((d) => config.docTypes.includes(d.id));
  const aiLimitExceeded = !forcedOffline && provider.id !== "offline" && config.employeeCount > LIMITS.maxEmployeesWithAi;

  return {
    settings,
    setSettings,
    provider,
    forcedOffline,
    presetId,
    choosePreset,
    config,
    setConfig,
    step,
    setStep,
    employees,
    personaCorrections,
    personaSource,
    personaRun,
    generatePersonas,
    updateEmployee,
    storylines,
    storyCorrections,
    storySource,
    storyRun,
    generateStorylines,
    updateStoryline,
    exchanges,
    stop,
    set,
    pkg,
    xml,
    report,
    breakers,
    applyBreaker,
    clearBreakers: () => setBreakers([]),
    enabledTypes,
    aiLimitExceeded,
    resetGenerated,
  };
}

export type Generator = ReturnType<typeof useGenerator>;
