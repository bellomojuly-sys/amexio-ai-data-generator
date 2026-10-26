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
import { unzipSync, strFromU8 } from "fflate";
import type { CaseStage } from "../case/bridge";
import { caseExportFiles, ingestInput, readCaseFiles, renderCases, throughCases } from "../case/bridge";
import type { RunSettings } from "../case/fromCase";
import type { Case } from "../case/generated/case";
import { referenceCase, referenceRun } from "../case/reference";

export type StepId = "configure" | "personas" | "storylines" | "documents" | "validate" | "export";
export type PresetId = "example" | "small" | "volume" | "custom" | "reference" | "cases";

/** Case folders opened in the demo (R6): the bundled reference case, or folders from disk. */
export interface LoadedCases {
  cases: Case[];
  run: RunSettings;
  source: string;
  /** Folders from disk follow the settings in Configure; the reference case keeps AMEXIO's. */
  followConfig: boolean;
}

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
  const [loaded, setLoaded] = useState<LoadedCases | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [storyRun, setStoryRun] = useState<RunState>({ status: "idle" });
  const abortRef = useRef<AbortController | null>(null);

  const [presetOffline, setPresetOffline] = useState(false);
  const forcedOffline = presetId === "example" || presetOffline || !!loaded;
  const provider = useMemo(() => createProvider(forcedOffline ? { ...settings, provider: "offline" } : settings), [settings, forcedOffline]);

  /** Choosing a model in Model settings overrides a preset's "no AI" choice. */
  const setSettings = useCallback((s: ModelSettings) => {
    setSettingsState(s);
    saveSettings(s);
    setPresetOffline(false);
  }, []);

  const resetGenerated = useCallback(() => {
    abortRef.current?.abort();
    setLoaded(null);
    setLoadError(null);
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
      if (!keepPreset) setPresetId((id) => (id === "reference" || id === "cases" ? id : "custom"));
    },
    [],
  );

  /** R6: open the case model's reference case 100101 (bundled) with AMEXIO's run settings. */
  const loadReference = useCallback(() => {
    resetGenerated();
    const run = referenceRun();
    setPresetId("reference");
    setPresetOffline(true);
    setConfigState(cloneConfig(run.config));
    setLoaded({ cases: [referenceCase()], run, source: "Reference case 100101 (case_model/reference_dossier.golden.json)", followConfig: false });
  }, [resetGenerated]);

  /**
   * R6: open case folders from disk: a folder holding 100101/case.json ..., or
   * the ZIP this demo exports (its cases/ folder). The run settings (period,
   * document types, import options) are the ones in Configure.
   */
  const loadCaseFiles = useCallback(
    async (list: FileList | File[]) => {
      const files: Record<string, string> = {};
      try {
        for (const file of Array.from(list)) {
          if (file.name.toLowerCase().endsWith(".zip")) {
            const entries = unzipSync(new Uint8Array(await file.arrayBuffer()), { filter: (f) => f.name.endsWith(".json") });
            for (const [path, data] of Object.entries(entries)) files[path] = strFromU8(data);
          } else if (file.name.endsWith(".json")) {
            files[(file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name] = await file.text();
          }
        }
        const cases = readCaseFiles(files);
        if (!cases.length) throw new Error("No case folders found: pick a folder with 100101/case.json, cast.json, storyline.json and documents.json in it, or the demo's ZIP.");
        const keep = cloneConfig(config);
        resetGenerated();
        setPresetId("cases");
        setPresetOffline(true);
        setConfigState(keep);
        const names = [...new Set(Array.from(list).map((f) => ((f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name).split("/")[0]))];
        setLoaded({ cases, run: { config: keep }, source: `Case folders (${names.slice(0, 2).join(", ")}${names.length > 2 ? ", ..." : ""})`, followConfig: true });
      } catch (e) {
        setLoadError((e as Error)?.message ?? "These files could not be read as case folders.");
      }
    },
    [config, resetGenerated],
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
    setLoaded(null);
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

  /** The generation run, in the AI's format (generation.json). Documents never read it directly. */
  const generated: DossierSet | null = useMemo(() => {
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

  /**
   * The bridge: the run is written as case folders and read back; documents,
   * validation and export read the cases (src/case/bridge.ts).
   */
  const { stage, caseError } = useMemo((): { stage: CaseStage | null; caseError: string | null } => {
    try {
      if (loaded) return { stage: renderCases(loaded.cases, loaded.followConfig ? { ...loaded.run, config } : loaded.run), caseError: null };
      if (!generated) return { stage: null, caseError: null };
      return { stage: throughCases(generated), caseError: null };
    } catch (e) {
      return { stage: null, caseError: (e as Error)?.message ?? "The run could not be written as cases." };
    }
  }, [loaded, generated, config]);

  /** The facts as read back from the cases: what every document is made from. */
  const set: DossierSet | null = stage?.read.set ?? null;

  const pkg: DossierPackage | null = useMemo(() => {
    if (!stage) return null;
    if (!breakers.length) return stage.pkg;
    const p = expandDossiers(stage.read.set, stage.read.index);
    for (const b of breakers) BREAKERS.find((x) => x.id === b.id)?.apply(stage.read.set, p);
    return p;
  }, [stage, breakers]);

  /** cases/ in the ZIP: one folder per employee, plus the run as the case model's input (R2). */
  const caseFiles = useMemo(() => {
    if (!stage) return {};
    let input: ReturnType<typeof ingestInput> | undefined;
    try {
      input = generated ? ingestInput(generated) : undefined;
    } catch {
      input = undefined;
    }
    return caseExportFiles(stage, input);
  }, [stage, generated]);

  const xml = useMemo(() => (set && pkg ? buildImportXml(set, pkg) : ""), [set, pkg]);

  const report: ValidationReport | null = useMemo(() => {
    if (!set || !pkg) return null;
    return validate(set, pkg, {
      cases: stage?.cases,
      xml,
      parseXml: (text) => {
        if (typeof DOMParser === "undefined") return null;
        const doc = new DOMParser().parseFromString(text, "application/xml");
        const err = doc.getElementsByTagName("parsererror")[0];
        return err ? (err.textContent ?? "parse error").slice(0, 200) : null;
      },
    });
  }, [set, pkg, xml, stage]);

  const applyBreaker = useCallback(
    (id: string) => {
      if (!stage) return;
      const s = stage.read.set;
      const probe = expandDossiers(s, stage.read.index);
      for (const b of breakers) BREAKERS.find((x) => x.id === b.id)?.apply(s, probe);
      const note = BREAKERS.find((x) => x.id === id)?.apply(s, probe);
      if (note) setBreakers((list) => [...list, { id, note }]);
    },
    [stage, breakers],
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
    employees: loaded ? (stage?.read.set.employees ?? null) : employees,
    personaCorrections,
    personaSource: loaded ? loaded.source : personaSource,
    personaRun,
    generatePersonas,
    storylines: loaded ? (stage?.read.set.storylines ?? null) : storylines,
    storyCorrections,
    storySource: loaded ? loaded.source : storySource,
    storyRun,
    generateStorylines,
    exchanges,
    stop,
    set,
    /** What generation.json records: the run in the AI's format, or the facts read from opened cases. */
    record: generated ?? set,
    stage,
    caseError,
    caseFiles,
    loaded,
    loadError,
    loadReference,
    loadCaseFiles,
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
