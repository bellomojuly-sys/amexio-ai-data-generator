import type { ISODate } from "../model/dates";
import { addYears, minDate } from "../model/dates";
import type { Employee } from "../model/dossier";
import { fullName } from "../model/dossier";
import { buildTimeline } from "../model/timeline";
import { DOC_TYPES } from "../spec/doctypes";
import { pdfDate } from "../spec/format";
import type { DocumentInstance, PlanContext } from "../spec/types";
import type { DossierPackage, DossierSet, FolderNode, GenerationConfig, UpdateNode } from "./types";

/**
 * Step 4: turn personas + storylines into documents and folders.
 * Pure code, no AI: every document type's plan() reads the same facts.
 */

export function employeeFolderLocation(config: GenerationConfig): string {
  return `${config.target.rootLocation}:${config.target.rootFolder}`;
}

export function employeeFolderTitle(e: Employee): string {
  return `${e.id} ${fullName(e)}`;
}

export function managerLabelFor(e: Pick<Employee, "firstName" | "lastName">): string {
  return `${e.firstName.trim().charAt(0)}. ${e.lastName} (fictional)`;
}

export function windowStartFor(config: GenerationConfig): ISODate {
  if (config.history === "latest") return "1900-01-01";
  return addYears(config.asOf, -config.historyYears);
}

export function expandDossiers(set: DossierSet): DossierPackage {
  const { config, employees, storylines } = set;
  const byId = new Map(employees.map((e) => [e.id, e]));
  const timelines = new Map(employees.map((e) => [e.id, buildTimeline(e, storylines[e.id])]));
  const enabled = new Set(config.docTypes);
  const windowStart = windowStartFor(config);
  const rootLocation = employeeFolderLocation(config);

  const folders: FolderNode[] = [
    {
      location: config.target.rootLocation,
      title: config.target.rootFolder,
      description: config.target.rootFolderDescription,
    },
  ];
  const documents: DocumentInstance[] = [];

  for (const employee of employees) {
    const timeline = timelines.get(employee.id)!;
    const lastDay = timeline.endDate ? minDate(timeline.endDate, config.asOf) : config.asOf;
    const current = timeline.stateAt(lastDay);
    folders.push({
      location: rootLocation,
      title: employeeFolderTitle(employee),
      description: `Personnel file of ${fullName(employee)}, ${current.position} (${employee.department})`,
      employeeId: employee.id,
    });

    const managerAt = (date: ISODate) => {
      if (employee.managerName) return { label: employee.managerName };
      const manager = employee.managerId ? byId.get(employee.managerId) : undefined;
      if (manager && manager.id !== employee.id && timelines.get(manager.id)!.employedOn(date)) {
        return { label: managerLabelFor(manager), employeeId: manager.id };
      }
      return { label: config.company.directorName };
    };

    const ctx: PlanContext = {
      employee,
      timeline,
      company: config.company,
      asOf: config.asOf,
      windowStart,
      managerAt,
    };

    const usedTitles = new Set<string>();
    const usedFiles = new Set<string>();

    for (const spec of DOC_TYPES) {
      if (!enabled.has(spec.id)) continue;
      let drafts = spec.plan(ctx);
      if (config.history === "latest" && drafts.length > 1) drafts = drafts.slice(-1);
      const many = drafts.length > 1;

      for (const draft of drafts) {
        let title = many ? (draft.titleIfMany ?? draft.title) : draft.title;
        let titleNl = many ? (draft.titleNlIfMany ?? draft.titleNl) : draft.titleNl;
        if (usedTitles.has(title.toLowerCase())) {
          title = `${title} (${pdfDate(draft.date)})`;
          titleNl = `${titleNl} (${pdfDate(draft.date)})`;
        }
        usedTitles.add(title.toLowerCase());

        let fileName = many
          ? `${employee.id}_${spec.slug}_${draft.fileSuffix}.pdf`
          : `${employee.id}_${spec.slug}.pdf`;
        for (let n = 2; usedFiles.has(fileName); n++) {
          fileName = `${employee.id}_${spec.slug}_${draft.fileSuffix}_${n}.pdf`;
        }
        usedFiles.add(fileName);

        documents.push({
          key: `${employee.id}/${spec.id}/${draft.fileSuffix}`,
          docType: spec.id,
          employeeId: employee.id,
          date: draft.date,
          title,
          extraTitles: config.importOptions.dutchTitles ? { nl: titleNl } : {},
          description: draft.description,
          fileName,
          values: { ...draft.values },
          meta: { ...(draft.meta ?? {}) },
          tags: [...spec.tags],
          confidential: spec.confidential,
          acl: spec.acl.map((a) => ({ ...a })),
          action: config.importOptions.action,
          versionControl:
            spec.id === "employment_contract" && config.importOptions.versionControlContracts ? "MAJOR" : undefined,
          sourceEvent: draft.sourceEvent,
        });
      }
    }
  }

  applyOverrides(set, documents);
  const updates = set.updates ?? defaultUpdates(set, documents);
  return { folders, documents, updates };
}

function applyOverrides(set: DossierSet, documents: DocumentInstance[]) {
  for (const o of set.overrides) {
    const matches = documents.filter((d) => d.employeeId === o.employeeId && d.docType === o.docType);
    for (const d of matches) {
      if (o.set.title !== undefined) d.title = o.set.title;
      if (o.set.extraTitles !== undefined) d.extraTitles = { ...o.set.extraTitles };
      if (o.set.action !== undefined) d.action = o.set.action;
      if (o.set.versionControl !== undefined) d.versionControl = o.set.versionControl;
      if (o.set.description !== undefined) d.description = o.set.description;
    }
  }
}

function defaultUpdates(set: DossierSet, documents: DocumentInstance[]): UpdateNode[] {
  if (!set.config.importOptions.includeUpdateExample) return [];
  const payslips = documents.filter((d) => d.docType === "payslip");
  const last = payslips[payslips.length - 1];
  if (!last) return [];
  const employee = set.employees.find((e) => e.id === last.employeeId)!;
  return [
    {
      location: `${employeeFolderLocation(set.config)}:${employeeFolderTitle(employee)}`,
      title: last.title,
      description: `${last.description} (checked by payroll)`,
      documentKey: last.key,
    },
  ];
}

export function documentLocation(set: DossierSet, employeeId: string): string {
  const e = set.employees.find((x) => x.id === employeeId);
  if (!e) return employeeFolderLocation(set.config);
  return `${employeeFolderLocation(set.config)}:${employeeFolderTitle(e)}`;
}
