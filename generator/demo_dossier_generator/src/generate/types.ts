import type { ISODate } from "../model/dates";
import type { Correction, Employee, Storyline } from "../model/dossier";
import type { CompanyProfile, TargetProfile } from "../spec/target";
import type { DocTypeId, DocumentInstance } from "../spec/types";

export interface ScenarioMix {
  /** Share of employees who leave the company during the history (0-1). */
  leaverShare: number;
  /** Share hired on a temporary contract (0-1). Some get a permanent contract later. */
  temporaryShare: number;
  /** Share working part time (0-1). */
  partTimeShare: number;
  /** Share with at least one sick-leave period (0-1). */
  absenceShare: number;
  /** Allow promotions to a higher position. */
  promotions: boolean;
  /** Let the AI write a short manager comment on each appraisal. */
  appraisalComments: boolean;
}

export interface ImportOptions {
  /** Store contracts as major version 1.0 (<versioncontrol>), as in the example. */
  versionControlContracts: boolean;
  /** Add a Dutch title next to the English one on every document. */
  dutchTitles: boolean;
  /** create = new objects; sync = create or update if they exist (safe to re-run). */
  action: "create" | "sync";
  /** Add one action="update" node at the end, like the example. */
  includeUpdateExample: boolean;
}

export interface GenerationConfig {
  seed: number;
  /** Nothing in the dataset is dated after this day. */
  asOf: ISODate;
  employeeCount: number;
  departments: string[];
  earliestHire: ISODate;
  /** "latest" = one document per type per employee, like AMEXIO's example. "full" = the whole history. */
  history: "latest" | "full";
  /** How many years of recurring documents to include in "full" mode. */
  historyYears: number;
  docTypes: DocTypeId[];
  scenario: ScenarioMix;
  importOptions: ImportOptions;
  /** Extra instructions for the AI, treated as data ("a fast-growing IT team"). */
  scenarioNotes: string;
  company: CompanyProfile;
  target: TargetProfile;
}

export interface FolderNode {
  location: string;
  title: string;
  description: string;
  employeeId?: string;
}

export interface UpdateNode {
  location: string;
  title: string;
  description: string;
  documentKey?: string;
}

/** A change applied to one generated document (used by the AMEXIO example preset). */
export interface DocOverride {
  employeeId: string;
  docType: DocTypeId;
  set: {
    title?: string;
    extraTitles?: Record<string, string>;
    action?: "create" | "sync";
    versionControl?: "MAJOR" | "MINOR";
    description?: string;
  };
}

export interface DossierPackage {
  folders: FolderNode[];
  documents: DocumentInstance[];
  updates: UpdateNode[];
  /** Rendering from cases: documents a case lists that no template rule can make. */
  caseIssues?: { employeeId: string; message: string }[];
}

/** Where each step's content came from, for the README and the UI. */
export interface Provenance {
  personas?: string;
  storylines?: string;
}

/** The whole state of one generation run. */
export interface DossierSet {
  generationId: string;
  config: GenerationConfig;
  employees: Employee[];
  storylines: Record<string, Storyline>;
  corrections: Correction[];
  overrides: DocOverride[];
  /** Explicit update nodes (the example preset); otherwise derived from importOptions. */
  updates?: UpdateNode[];
  provenance: Provenance;
}
