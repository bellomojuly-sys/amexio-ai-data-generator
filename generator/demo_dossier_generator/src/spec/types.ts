import type { ISODate } from "../model/dates";
import type { Employee } from "../model/dossier";
import type { Timeline } from "../model/timeline";
import type { CompanyProfile } from "./target";

/**
 * The format spec, as TypeScript.
 *
 * Every document type is one module in ./doctypes that exports a DocTypeSpec:
 * which fields it has, how each value is formatted, where each value comes
 * from, what metadata and access rights it gets in Content Server, and when it
 * occurs in an employee's history. The generator, the PDF renderer, the XML
 * exporter, the validator and the UI all read from these modules, so adding a
 * document type means adding one file and registering it in doctypes/index.ts.
 */

export type DocTypeId =
  | "employment_contract"
  | "payslip"
  | "medical_check"
  | "performance_appraisal"
  | "training_certificate"
  | "contract_amendment"
  | "annual_income_statement"
  | "absence_report"
  | "termination_letter";

/** Where a value in a document comes from. The UI can colour values by origin. */
export type ValueOrigin =
  /** From the persona (AI proposal, reviewed by the user, checked by code). */
  | "persona"
  /** From the storyline (AI proposal, reviewed by the user, checked by code). */
  | "storyline"
  /** Calculated by code from other facts (tax, net pay, next check date...). */
  | "rule"
  /** A fixed value from the company or target-system profile. */
  | "constant"
  /** Free text written by the AI (appraisal comments). */
  | "ai-text";

export type FieldFormat =
  | "text"
  | "date" // DD-MM-YYYY
  | "dateRange" // DD-MM-YYYY to DD-MM-YYYY
  | "monthYear" // September 2026
  | "eurGrouped" // EUR 4.350
  | "eurPlain" // EUR 4350
  | "days" // 2 days
  | "number";

export type FieldValue = string | number | { from: ISODate; to: ISODate };

export interface FieldDef {
  key: string;
  /** Label as printed in the PDF, without the colon. */
  label: string;
  format: FieldFormat;
  origin: ValueOrigin;
  /** A missing optional field is left out of the PDF. */
  optional?: boolean;
  /** How the value is derived, in words. Shown in the UI and in format-spec.json. */
  rule?: string;
}

export interface AclEntry {
  /** A Content Server group, e.g. "HR Medical". Must already exist in the target system. */
  group?: string;
  /** A standard ACL entry, e.g. "world". */
  standard?: string;
  /** Nine switches, "1" = on. Meaning per position: see notes, to be confirmed with AMEXIO. */
  permissions: string;
}

/** What a document type's plan() returns: one future document, before shared metadata is added. */
export interface DocDraft {
  /** The document's key date: created = modified = Document Date = the date printed in the PDF. */
  date: ISODate;
  title: string;
  titleNl: string;
  /** Title to use when the employee has more than one document of this type (titles must be unique per folder). */
  titleIfMany?: string;
  titleNlIfMany?: string;
  description: string;
  values: Record<string, FieldValue | undefined>;
  /** Facts that are not printed but that the validator needs (e.g. the manager's employee ID). */
  meta?: Record<string, string>;
  /** Makes the file name unique when an employee has more than one document of this type. */
  fileSuffix: string;
  /** Index into the storyline's events, for traceability. */
  sourceEvent?: number;
}

export interface PlanContext {
  employee: Employee;
  timeline: Timeline;
  company: CompanyProfile;
  /** The "as of" date of the dataset: nothing is dated after it. */
  asOf: ISODate;
  /** First date for recurring documents (payslips, statements...). */
  windowStart: ISODate;
  /** Who signs an appraisal on a given date: the department manager if employed then, else the director. */
  managerAt(date: ISODate): { label: string; employeeId?: string };
}

export interface DocTypeSpec {
  id: DocTypeId;
  /** Value of the "Document Type" category attribute. */
  documentType: string;
  /** File name part: {employeeId}_{slug}[_{suffix}].pdf */
  slug: string;
  /** "amexio" = in AMEXIO's example package; "extension" = our proposal, to confirm with AMEXIO. */
  origin: "amexio" | "extension";
  summary: string;
  /** When it occurs, in words. */
  occurs: string;
  titlePattern: string;
  tags: string[];
  confidential: boolean;
  acl: AclEntry[];
  fields: FieldDef[];
  /** The field that prints the document date (must equal <created> and Document Date). */
  dateField?: string;
  /** Cross-document rules this type must satisfy, in words. */
  rules: string[];
  /** Lists every document of this type in the employee's history, oldest first. */
  plan(ctx: PlanContext): DocDraft[];
}

/** One generated document: the PDF and its node in import.xml. */
export interface DocumentInstance {
  key: string;
  docType: DocTypeId;
  employeeId: string;
  date: ISODate;
  title: string;
  /** Extra titles by language code, e.g. { nl: "Loonstrook september 2026" }. */
  extraTitles: Record<string, string>;
  description: string;
  fileName: string;
  values: Record<string, FieldValue | undefined>;
  meta: Record<string, string>;
  tags: string[];
  confidential: boolean;
  acl: AclEntry[];
  action: "create" | "sync";
  versionControl?: "MAJOR" | "MINOR";
  sourceEvent?: number;
}

/** A row as printed in the PDF. */
export interface RenderedRow {
  label: string;
  value: string;
  origin: ValueOrigin;
  fieldKey: string;
}

/** Everything the PDF shows, in order. The HTML preview uses the same structure. */
export interface RenderedDocument {
  banner: string;
  title: string;
  identity: RenderedRow[];
  rows: RenderedRow[];
  footer: string;
  /** PDF metadata title: "{title} - {full name}" in the example. */
  pdfTitle: string;
}
