import type { ISODate } from "../model/dates";
import type { CareerEvent, Employee, Storyline } from "../model/dossier";
import { eventDate } from "../model/dossier";
import type { DocOverride, DossierSet, GenerationConfig, Provenance, UpdateNode } from "../generate/types";
import type { Correction } from "../model/dossier";
import type { Signer } from "../generate/expand";
import type { Case, Events, Persona } from "./generated/case";
import { checkCase } from "./checkCase";
import type { CompanyProfile } from "../spec/target";

/**
 * The reader (R6): saved cases back into what the document templates read.
 *
 * Every fact a PDF or import.xml prints comes from here: the employee and the
 * job from the persona and the employment, the history from the events, the
 * appraisal's manager from the appraisal's participants, the provider and the
 * examiner from the case's organisations and personas. The run configuration
 * (period, document types, import options) is not part of a case and comes
 * from the caller.
 */

export interface CaseDocRef {
  id: string;
  type: string;
  date: ISODate;
  eventId: string | null;
  participantIds: string[];
  confidential: boolean;
  tags: string[];
}

/** One employee's case, indexed for the document templates. */
export interface CaseView {
  caseNumber: string;
  /** The case's event IDs, in the order of the timeline's events (index = DocDraft.sourceEvent). */
  eventIds: string[];
  hireEventId?: string;
  /** The documents the case lists. Empty: the templates decide, as for a case from ingest.py. */
  documents: CaseDocRef[];
  folderDescription: string | null;
  /** Employer, training provider, examiner and occupational health service, as this case holds them. */
  company: CompanyProfile;
  managerAt(date: ISODate): Signer;
}

export interface CaseIndex {
  byEmployee: Map<string, CaseView>;
}

export interface CaseRead {
  /** The facts in the generator's own shape, for plan(), the PDFs and import.xml. */
  set: DossierSet;
  index: CaseIndex;
  /** Everything the case model would refuse (checkCase), and anything the reader could not place. */
  problems: { employeeId?: string; message: string }[];
}

export interface RunSettings {
  config: GenerationConfig;
  generationId?: string;
  overrides?: DocOverride[];
  updates?: UpdateNode[];
  corrections?: Correction[];
  provenance?: Provenance;
}

export function matchCaseDocument(view: CaseView, type: string, date: ISODate, eventId: string | null | undefined): CaseDocRef | undefined {
  return view.documents.find(
    (d) => d.type === type && d.date === date && (eventId === undefined || d.eventId === eventId),
  );
}

const byId = <T extends { id: string }>(record: Record<string, T> | undefined) =>
  Object.values(record ?? {}).sort((a, b) => a.id.localeCompare(b.id));

function splitName(name: string): { firstName: string; lastName: string } {
  const parts = name.trim().split(/\s+/);
  return { firstName: parts[0] ?? "", lastName: parts.slice(1).join(" ") };
}

function careerEvent(e: Events[string]): CareerEvent | null {
  switch (e.type) {
    case "hire":
      return null;
    case "contract_change":
      return {
        type: "contract_change",
        date: e.date,
        reason: e.reason,
        ...(e.new_salary ? { newSalary: Number(e.new_salary.amount) } : {}),
        ...(e.new_position ? { newPosition: e.new_position } : {}),
        ...(e.new_contract_type ? { newContractType: e.new_contract_type } : {}),
        ...(e.new_hours != null ? { newHours: e.new_hours } : {}),
      };
    case "training":
      return { type: "training", date: e.date, course: e.course, durationDays: e.duration_days };
    case "appraisal":
      return { type: "appraisal", year: e.year, rating: e.rating, ...(e.comment ? { comment: e.comment } : {}) };
    case "medical_check":
      return { type: "medical_check", date: e.date, result: e.result };
    case "absence":
      return { type: "absence", startDate: e.date, ...(e.end_date ? { endDate: e.end_date } : {}) };
    case "termination":
      return { type: "termination", date: e.date, reason: e.reason, ...(e.notice_date ? { noticeDate: e.notice_date } : {}) };
  }
}

/**
 * The organisations and the examiner a case holds. A part the case does not
 * hold stays empty, so the document that needs it shows the gap (and the
 * validator blocks it) instead of printing a default.
 */
function companyOf(c: Case, directorName: string): CompanyProfile {
  const orgs = byId(c.organisations);
  const org = (kind: string) => orgs.find((o) => o.kind === kind)?.name ?? "";
  return {
    employerName: org("employer"),
    trainingProvider: org("training_provider"),
    examiner: byId(c.personas).find((p) => p.role === "examiner")?.name ?? "",
    absenceService: org("occupational_health"),
    directorName,
  };
}

/** Reads cases into the generator's facts. The cases should come from caseFolder()/readCaseFolder() or be checked. */
export function fromCases(cases: Case[], run: RunSettings): CaseRead {
  const problems: CaseRead["problems"] = [];
  const config: GenerationConfig = { ...run.config, company: { ...run.config.company } };
  const ordered = [...cases].sort((a, b) => a.case_number.localeCompare(b.case_number));

  for (const c of ordered) {
    for (const message of checkCase(c)) problems.push({ employeeId: c.case_number, message });
  }

  // The set-level company profile (README, generation.json) is the first case's; each
  // document prints the company of its own case (CaseView.company).
  if (ordered[0]) config.company = companyOf(ordered[0], config.company.directorName);

  // Employee numbers by name, so an appraisal signed by a colleague links to that colleague's dossier.
  const numberByName = new Map<string, string>();
  for (const c of ordered) {
    const self = byId(c.personas).find((p) => p.role === "employee");
    if (self) numberByName.set(self.name, c.dossier.employee_number);
  }

  const employees: Employee[] = [];
  const storylines: Record<string, Storyline> = {};
  const index: CaseIndex = { byEmployee: new Map() };

  for (const c of ordered) {
    const number = c.dossier.employee_number;
    const personas = c.personas ?? {};
    const self = byId(personas).find((p) => p.role === "employee");
    const job = (c.employments ?? []).find((j) => j.persona_id === self?.id) ?? c.employments?.[0];
    if (!self || !job) {
      problems.push({ employeeId: number, message: `Case ${number} has no employee persona with an employment; it is left out.` });
      continue;
    }
    const managersList = byId(personas).filter((p) => p.role === "manager");
    const mainManager: Persona | undefined = managersList[0];
    const allEvents = byId(c.events);
    const termination = allEvents.find((e) => e.type === "termination");

    // Timeline order: by date (an appraisal on 30 June), then by ID, the same stable order buildTimeline uses.
    const story = allEvents
      .map((e) => ({ id: e.id, event: careerEvent(e) }))
      .filter((x): x is { id: string; event: CareerEvent } => x.event !== null)
      .map((x, i) => ({ ...x, i }))
      .sort((a, b) => eventDate(a.event).localeCompare(eventDate(b.event)) || a.i - b.i);

    const managerNumber = mainManager ? numberByName.get(mainManager.name) : undefined;
    employees.push({
      id: number,
      ...splitName(self.name),
      department: job.department,
      position: job.position,
      hireDate: job.start_date,
      contractType: job.contract_type,
      hoursPerWeek: job.hours,
      startSalary: Number(job.salary.amount),
      isManager: ordered.some(
        (other) => other !== c && byId(other.personas).some((p) => p.role === "manager" && p.name === self.name),
      ),
      ...(managerNumber && managerNumber !== number ? { managerId: managerNumber } : mainManager ? { managerName: mainManager.name } : {}),
      leaves: !!termination,
    });
    storylines[number] = { employeeId: number, events: story.map((x) => x.event) };

    const appraisalSigner = new Map<ISODate, Signer>();
    for (const e of allEvents) {
      if (e.type !== "appraisal") continue;
      const signer = e.participant_ids.map((pid) => personas[pid]).find((p) => p && p.role === "manager");
      if (signer) appraisalSigner.set(e.date, { label: signer.name, employeeId: numberByName.get(signer.name) });
    }
    const fallback: Signer = mainManager
      ? { label: mainManager.name, employeeId: numberByName.get(mainManager.name) }
      : { label: config.company.directorName };

    index.byEmployee.set(number, {
      caseNumber: c.case_number,
      eventIds: story.map((x) => x.id),
      hireEventId: allEvents.find((e) => e.type === "hire")?.id,
      documents: byId(c.documents).map((d) => ({
        id: d.id,
        type: d.type,
        date: d.metadata.document_date,
        eventId: d.event_id ?? null,
        participantIds: [...d.participant_ids],
        confidential: d.metadata.confidential,
        tags: [...(d.metadata.tags ?? [])],
      })),
      folderDescription: c.dossier.description ?? null,
      company: companyOf(c, config.company.directorName),
      managerAt: (date) => {
        const s = appraisalSigner.get(date) ?? fallback;
        return s.employeeId && s.employeeId !== number ? s : { label: s.label };
      },
    });
  }

  const set: DossierSet = {
    generationId: run.generationId ?? `CASES-${ordered.map((c) => c.case_number).join("-").slice(0, 40)}`,
    config: { ...config, employeeCount: employees.length },
    employees,
    storylines,
    corrections: run.corrections ?? [],
    overrides: run.overrides ?? [],
    ...(run.updates ? { updates: run.updates } : {}),
    provenance: run.provenance ?? { personas: "case folders", storylines: "case folders" },
  };
  return { set, index, problems };
}

/** The persona's printed name, for the UI: "P002 M. Bakker (fictional), manager". */
export function personaLabel(c: Case, id: string): string {
  const p = c.personas?.[id];
  return p ? `${id} ${p.name}, ${p.role}` : id;
}
