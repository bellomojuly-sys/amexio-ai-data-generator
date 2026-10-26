import type { ISODate } from "../model/dates";
import { addYears, minDate } from "../model/dates";
import type { Employee } from "../model/dossier";
import { fullName } from "../model/dossier";
import { buildTimeline } from "../model/timeline";
import type { Timeline } from "../model/timeline";
import { DOC_TYPES } from "../spec/doctypes";
import { pdfDate } from "../spec/format";
import type { DocumentInstance, PlanContext } from "../spec/types";
import type { CaseIndex, CaseView } from "../case/fromCase";
import { matchCaseDocument } from "../case/fromCase";
import type { DossierPackage, DossierSet, FolderNode, GenerationConfig, UpdateNode } from "./types";

/**
 * Step 4: turn personas + storylines into documents and folders.
 * Pure code, no AI: every document type's plan() reads the same facts.
 *
 * With a CaseIndex (src/case/fromCase.ts) the facts come from saved cases:
 * each document gets the case's DOC and EVT IDs, and when a case lists its
 * documents, the case decides which documents exist.
 */

export function employeeFolderLocation(config: GenerationConfig): string {
  return `${config.target.rootLocation}:${config.target.rootFolder}`;
}

export function employeeFolderTitle(e: Employee): string {
  return `${e.id} ${fullName(e)}`;
}

export interface Signer {
  label: string;
  employeeId?: string;
}

/**
 * Who signs an employee's appraisal on a date: the free-text manager when the
 * manager is not in the dataset (AMEXIO's example), else the department
 * manager if employed on that date, else the director. The case model stores
 * the result as the appraisal's manager participant.
 */
export function managerResolver(set: DossierSet, timelines: Map<string, Timeline>) {
  const byId = new Map(set.employees.map((e) => [e.id, e]));
  return (employee: Employee) =>
    (date: ISODate): Signer => {
      if (employee.managerName) return { label: employee.managerName };
      const manager = employee.managerId ? byId.get(employee.managerId) : undefined;
      if (manager && manager.id !== employee.id && timelines.get(manager.id)?.employedOn(date)) {
        return { label: fullName(manager), employeeId: manager.id };
      }
      return { label: set.config.company.directorName };
    };
}

/** The manager the case model files for an employee (P002), as ingest.py picks it. */
export function caseManagerName(set: DossierSet, employee: Employee): string {
  if (employee.managerName) return employee.managerName;
  const manager = employee.managerId ? set.employees.find((e) => e.id === employee.managerId) : undefined;
  return manager ? fullName(manager) : set.config.company.directorName;
}

export function windowStartFor(config: GenerationConfig): ISODate {
  if (config.history === "latest") return "1900-01-01";
  return addYears(config.asOf, -config.historyYears);
}

export function expandDossiers(set: DossierSet, cases?: CaseIndex): DossierPackage {
  const { config, employees, storylines } = set;
  const timelines = new Map(employees.map((e) => [e.id, buildTimeline(e, storylines[e.id])]));
  const enabled = new Set(config.docTypes);
  const rootLocation = employeeFolderLocation(config);
  const signerFor = managerResolver(set, timelines);
  const caseIssues: { employeeId: string; message: string }[] = [];

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
    const view: CaseView | undefined = cases?.byEmployee.get(employee.id);
    // When the case lists its documents, the case decides which exist: plan() lists every possible one.
    const caseDriven = !!view && view.documents.length > 0;
    folders.push({
      location: rootLocation,
      title: employeeFolderTitle(employee),
      description:
        view?.folderDescription ?? `Personnel file of ${fullName(employee)}, ${current.position} (${employee.department})`,
      employeeId: employee.id,
    });

    const ctx: PlanContext = {
      employee,
      timeline,
      company: view?.company ?? config.company,
      asOf: config.asOf,
      windowStart: caseDriven ? "1900-01-01" : windowStartFor(config),
      managerAt: view ? view.managerAt : signerFor(employee),
    };
    const matched = new Set<string>();

    const usedTitles = new Set<string>();
    const usedFiles = new Set<string>();

    for (const spec of DOC_TYPES) {
      if (!enabled.has(spec.id)) continue;
      const eventIdOf = (sourceEvent?: number) =>
        !view ? undefined
        : spec.id === "employment_contract" ? (view.hireEventId ?? null)
        : sourceEvent !== undefined ? (view.eventIds[sourceEvent] ?? null)
        : null;
      let drafts = spec.plan(ctx);
      if (caseDriven) {
        drafts = drafts.filter((d) => matchCaseDocument(view!, spec.id, d.date, eventIdOf(d.sourceEvent)) !== undefined);
      } else if (config.history === "latest" && drafts.length > 1) {
        drafts = drafts.slice(-1);
      }
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

        const eventId = eventIdOf(draft.sourceEvent);
        const caseDoc = view ? matchCaseDocument(view, spec.id, draft.date, eventId) : undefined;
        if (caseDoc) matched.add(caseDoc.id);
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
          tags: caseDoc ? [...caseDoc.tags] : [...spec.tags],
          confidential: caseDoc ? caseDoc.confidential : spec.confidential,
          acl: spec.acl.map((a) => ({ ...a })),
          action: config.importOptions.action,
          versionControl:
            spec.id === "employment_contract" && config.importOptions.versionControlContracts ? "MAJOR" : undefined,
          sourceEvent: draft.sourceEvent,
          ...(view ? { caseEventId: eventId ?? null, caseDocId: caseDoc?.id, participantIds: caseDoc?.participantIds } : {}),
        });
      }
    }

    if (caseDriven) {
      for (const d of view!.documents) {
        if (matched.has(d.id)) continue;
        caseIssues.push({
          employeeId: employee.id,
          message: enabled.has(d.type as never)
            ? `${d.id} (${d.type}, ${d.date}) cannot be rendered: no template rule makes a ${d.type} on that date${d.eventId ? ` for ${d.eventId}` : ""}.`
            : `${d.id} (${d.type}) is not rendered: that document type is switched off in this run.`,
        });
      }
    }
  }

  applyOverrides(set, documents);
  const updates = set.updates ?? defaultUpdates(set, documents);
  return cases ? { folders, documents, updates, caseIssues } : { folders, documents, updates };
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
