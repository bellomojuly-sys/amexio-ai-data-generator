import { expandDossiers } from "../generate/expand";
import type { DossierPackage, DossierSet } from "../generate/types";
import type { CareerEvent } from "../model/dossier";
import { caseFolderFiles, readCaseFolder } from "./caseJson";
import type { CaseRead, RunSettings } from "./fromCase";
import { fromCases } from "./fromCase";
import type { Case } from "./generated/case";
import type { EmployeesIn } from "./generated/inputEmployees";
import type { StorylinesIn } from "./generated/inputStorylines";
import { toCases } from "./toCase";

/**
 * The whole bridge in one place (ROADMAP_BRIDGE.md):
 *
 *   generation run ─▶ toCases ─▶ case folders (4 JSON files each)
 *                                    │  read back, as a reader would
 *                                    ▼
 *                 fromCases ─▶ plan() ─▶ PDFs + import.xml
 *
 * Documents and export never read the in-memory run: they read the cases,
 * after a real write and read of the files.
 */

export interface CaseStage {
  /** The cases as read back from their files. */
  cases: Case[];
  /** "100101/case.json" ... exactly as save_case writes them. */
  files: Record<string, string>;
  read: CaseRead;
  /** The documents and folders, rendered from the cases. */
  pkg: DossierPackage;
}

/** Groups "100101/case.json"-style paths by folder and reads every folder that holds a case.json. */
export function readCaseFiles(files: Record<string, string>): Case[] {
  const folders = new Map<string, Record<string, string>>();
  for (const [path, text] of Object.entries(files)) {
    const parts = path.split("/");
    const name = parts.pop()!;
    const folder = parts.join("/");
    folders.set(folder, { ...(folders.get(folder) ?? {}), [name]: text });
  }
  return [...folders.entries()]
    .filter(([, f]) => "case.json" in f)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([folder, f]) => readCaseFolder(f, folder || "case folder"));
}

export function runSettingsOf(set: DossierSet): RunSettings {
  return {
    config: set.config,
    generationId: set.generationId,
    overrides: set.overrides,
    updates: set.updates,
    corrections: set.corrections,
    provenance: set.provenance,
  };
}

/** Renders saved cases: the reader plus plan(). */
export function renderCases(cases: Case[], run: RunSettings): CaseStage {
  const read = fromCases(cases, run);
  const pkg = expandDossiers(read.set, read.index);
  return { cases, files: caseFolderFiles(cases), read, pkg };
}

/** A generation run through the case model's format and back. */
export function throughCases(set: DossierSet): CaseStage {
  const files = caseFolderFiles(toCases(set, expandDossiers(set)));
  return renderCases(readCaseFiles(files), runSettingsOf(set));
}

/**
 * R2 — the run as the case model's input files (`python -m case_model.ingest
 * employees.json storylines.json --out DIR`). These are the facts after the
 * demo's own checks, in the shapes of case_model/schema/input.*.schema.json;
 * ingest gives the same cases as toCases, without the documents.
 */
export function ingestInput(set: DossierSet): { employees: EmployeesIn; storylines: StorylinesIn } {
  const c = set.config.company;
  const employees = set.employees.map((e) => {
    // ingest.py: without managerName, the manager is the department's isManager employee, and a
    // manager reports to the director. The demo also lets the director sign when a department has
    // no manager, so that case is written out.
    const managerName = e.managerName ?? (!e.managerId && !e.isManager ? c.directorName : undefined);
    return {
      firstName: e.firstName,
      lastName: e.lastName,
      department: e.department,
      position: e.position,
      isManager: e.isManager,
      hireDate: e.hireDate,
      contractType: e.contractType,
      hoursPerWeek: e.hoursPerWeek,
      startSalary: e.startSalary,
      ...(managerName ? { managerName } : {}),
    };
  });
  if (!employees.length) throw new Error("A run without employees has no input to write.");
  return {
    employees: {
      company: {
        employerName: c.employerName,
        trainingProvider: c.trainingProvider,
        examiner: c.examiner,
        absenceService: c.absenceService,
        directorName: c.directorName,
      },
      employees: employees as EmployeesIn["employees"],
    },
    storylines: {
      storylines: set.employees.map((e) => ({
        employeeId: e.id,
        events: (set.storylines[e.id]?.events ?? []).map(inputEvent),
      })),
    },
  };
}

function inputEvent(e: CareerEvent): StorylinesIn["storylines"][number]["events"] extends (infer T)[] | undefined ? T : never {
  switch (e.type) {
    case "contract_change":
      return {
        type: "contract_change",
        date: e.date,
        reason: e.reason,
        ...(e.newSalary !== undefined ? { newSalary: e.newSalary } : {}),
        ...(e.newPosition !== undefined ? { newPosition: e.newPosition } : {}),
        ...(e.newContractType !== undefined ? { newContractType: e.newContractType } : {}),
        ...(e.newHours !== undefined ? { newHours: e.newHours } : {}),
      };
    case "training":
      return { type: "training", date: e.date, course: e.course, durationDays: e.durationDays };
    case "appraisal":
      return { type: "appraisal", year: e.year, rating: e.rating, ...(e.comment ? { comment: e.comment } : {}) };
    case "medical_check":
      return { type: "medical_check", date: e.date, result: e.result };
    case "absence":
      return { type: "absence", startDate: e.startDate, ...(e.endDate ? { endDate: e.endDate } : {}) };
    case "termination":
      return { type: "termination", date: e.date, reason: e.reason, ...(e.noticeDate ? { noticeDate: e.noticeDate } : {}) };
  }
}

/** Files for the ZIP: the case folders and the ingest input, under `cases/`. */
export function caseExportFiles(stage: Pick<CaseStage, "files">, input?: ReturnType<typeof ingestInput>): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [path, text] of Object.entries(stage.files)) out[`cases/${path}`] = text;
  if (input) {
    out["cases/employees.json"] = JSON.stringify(input.employees, null, 2) + "\n";
    out["cases/storylines.json"] = JSON.stringify(input.storylines, null, 2) + "\n";
  }
  return out;
}
