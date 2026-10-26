import { DEFAULT_COMPANY, DEFAULT_TARGET } from "../spec/target";
import { DOC_TYPES } from "../spec/doctypes";
import type { GenerationConfig } from "./types";
import { DEFAULT_DEPARTMENTS } from "./vocab";

export const DEFAULT_CONFIG: GenerationConfig = {
  seed: 2026,
  asOf: "2026-09-30",
  employeeCount: 10,
  departments: [...DEFAULT_DEPARTMENTS],
  earliestHire: "2015-01-01",
  history: "full",
  historyYears: 3,
  docTypes: DOC_TYPES.map((d) => d.id),
  scenario: {
    leaverShare: 0.2,
    temporaryShare: 0.2,
    partTimeShare: 0.2,
    absenceShare: 0.3,
    promotions: true,
    appraisalComments: true,
  },
  importOptions: {
    versionControlContracts: false,
    dutchTitles: false,
    action: "create",
    includeUpdateExample: false,
  },
  scenarioNotes: "",
  company: { ...DEFAULT_COMPANY },
  target: { ...DEFAULT_TARGET },
};

export function cloneConfig(c: GenerationConfig): GenerationConfig {
  return JSON.parse(JSON.stringify(c)) as GenerationConfig;
}

/** Hard limits for the live demo, so one click cannot run up a huge model bill. */
export const LIMITS = {
  maxEmployeesWithAi: 25,
  maxEmployeesOffline: 250,
  maxHistoryYears: 12,
  storylineBatchSize: 5,
};

export function newGenerationId(seed: number): string {
  const stamp = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 12);
  return `GEN-${stamp}-${seed}`;
}
