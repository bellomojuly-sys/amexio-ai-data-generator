import type { ISODate } from "../model/dates";
import type { CareerEvent, Employee } from "../model/dossier";
import { fullName } from "../model/dossier";
import { buildTimeline } from "../model/timeline";
import type { Timeline } from "../model/timeline";
import { caseManagerName, employeeFolderTitle, expandDossiers, managerResolver } from "../generate/expand";
import type { DossierPackage, DossierSet } from "../generate/types";
import { DOC_TYPES } from "../spec/doctypes";
import type { DocumentInstance } from "../spec/types";
import { RECURRING_DOCUMENT_TYPES } from "./checkCase";
import type { Case, Document, Events, Money, Organisation, Persona } from "./generated/case";

/**
 * The bridge: one generation run (DossierSet) becomes one case per employee,
 * in the case model's format (case_model/schema/case.schema.json).
 *
 * The cases are built the way case_model/ingest.py builds them from the same
 * facts, so both paths end in the same case folders:
 *
 *   P001 the employee, P002 their manager, P003 the examiner
 *   ORG-01 employer, ORG-02 training provider, ORG-03 occupational health
 *   EVT-001 the hire, then every storyline event in date order
 *   DOC-001... every document in date order, each pointing at the event it
 *   records (a payslip or annual statement points at none)
 *
 * Field names are snake_case, amounts are Money ({amount: "4350.00",
 * currency: "EUR"}), an appraisal is dated 30 June of its year, and a value
 * the case model has no field for stays out (it is a template rule, see
 * docs/HANDOFF_GIULIA.md, R4).
 */

export const CURRENCY = "EUR";

export function money(amount: number): Money {
  return { amount: amount.toFixed(2), currency: CURRENCY };
}

const pad = (n: number, digits: number) => String(n).padStart(digits, "0");
export const personaId = (n: number) => `P${pad(n, 3)}`;
export const organisationId = (n: number) => `ORG-${pad(n, 2)}`;
export const eventId = (n: number) => `EVT-${pad(n, 3)}`;
export const documentId = (n: number) => `DOC-${pad(n, 3)}`;

export class CaseBuildError extends Error {}

/** All cases of a run. `pkg` is the run's documents; without it they are planned here. */
export function toCases(set: DossierSet, pkg: DossierPackage = expandDossiers(set)): Case[] {
  const timelines = new Map(set.employees.map((e) => [e.id, buildTimeline(e, set.storylines[e.id])]));
  const signerFor = managerResolver(set, timelines);
  const docsByEmployee = new Map<string, DocumentInstance[]>();
  for (const d of pkg.documents) docsByEmployee.set(d.employeeId, [...(docsByEmployee.get(d.employeeId) ?? []), d]);
  return set.employees.map((e) =>
    toCase(set, e, timelines.get(e.id)!, signerFor(e), docsByEmployee.get(e.id) ?? []),
  );
}

function toCase(
  set: DossierSet,
  employee: Employee,
  timeline: Timeline,
  signerAt: (date: ISODate) => { label: string },
  docs: DocumentInstance[],
): Case {
  const company = set.config.company;
  const number = employee.id;
  const name = fullName(employee);

  // Parts get their IDs in the order ingest.py adds them.
  const personas: Record<string, Persona> = {};
  const organisations: Record<string, Organisation> = {};
  const addOrganisation = (orgName: string, kind: string) => {
    const id = organisationId(Object.keys(organisations).length + 1);
    organisations[id] = { address: null, id, kind, name: orgName };
    return id;
  };
  const addPersona = (personaName: string, role: Persona["role"], organisation: string | null) => {
    const id = personaId(Object.keys(personas).length + 1);
    personas[id] = { address: null, date_of_birth: null, id, name: personaName, organisation_id: organisation, role, salutation: null };
    return id;
  };

  const employer = addOrganisation(company.employerName, "employer");
  const self = addPersona(name, "employee", employer);
  const managerName = caseManagerName(set, employee);
  const managers = new Map<string, string>();
  if (managerName && managerName !== name) managers.set(managerName, addPersona(managerName, "manager", employer));
  const provider = company.trainingProvider ? addOrganisation(company.trainingProvider, "training_provider") : undefined;
  let examiner: string | undefined;
  if (company.examiner) {
    const service = company.absenceService ? addOrganisation(company.absenceService, "occupational_health") : null;
    examiner = addPersona(company.examiner, "examiner", service);
  }
  /** Whoever signs an appraisal; someone other than P002 (the director, when the manager had left) is added once. */
  const managerPersona = (signer: string) => {
    if (signer === name) throw new CaseBuildError(`${number}: the employee cannot sign their own appraisal.`);
    if (!managers.has(signer)) managers.set(signer, addPersona(signer, "manager", employer));
    return managers.get(signer)!;
  };

  // EVT-001 is the hire; the storyline follows in the timeline's (date) order,
  // so the timeline's event index i is EVT-(i + 2): that is how a document's
  // sourceEvent becomes its event_id.
  const events: Events = {};
  const hire = eventId(1);
  events[hire] = { date: employee.hireDate, id: hire, label: null, participant_ids: [self], summary: null, type: "hire" };
  const eventIds = timeline.events.map((_, i) => eventId(i + 2));
  timeline.events.forEach((e, i) => {
    events[eventIds[i]] = caseEvent(e, eventIds[i], self, {
      provider,
      examiner,
      manager: e.type === "appraisal" ? managerPersona(signerAt(`${e.year}-06-30`).label) : undefined,
      number,
    });
  });

  // DOC-001... in date order; on the same date, in the order of the document types.
  const typeOrder = new Map(DOC_TYPES.map((d, i) => [d.id, i]));
  const ordered = docs
    .map((d, i) => ({ d, i }))
    .sort((a, b) => a.d.date.localeCompare(b.d.date) || typeOrder.get(a.d.docType)! - typeOrder.get(b.d.docType)! || a.i - b.i)
    .map((x) => x.d);
  const documents: Record<string, Document> = {};
  ordered.forEach((d, i) => {
    const id = documentId(i + 1);
    let event: string | null = null;
    if (d.docType === "employment_contract") event = hire;
    else if (d.sourceEvent !== undefined) event = eventIds[d.sourceEvent] ?? null;
    if (event === null && !RECURRING_DOCUMENT_TYPES.has(d.docType)) {
      throw new CaseBuildError(`${number}: ${d.title} (${d.date}) records no event, but a ${d.docType} needs one.`);
    }
    documents[id] = {
      event_id: event,
      id,
      metadata: {
        confidential: d.confidential,
        document_date: d.date,
        document_type: d.docType,
        employee_id: number,
        tags: [...d.tags],
      },
      participant_ids: event ? [...events[event].participant_ids] : [self],
      text: null,
      type: d.docType,
    };
  });

  return {
    case_number: number,
    documents,
    dossier: { description: null, employee_number: number, folder_title: employeeFolderTitle(employee) },
    employments: [
      {
        contract_type: employee.contractType,
        department: employee.department,
        hours: employee.hoursPerWeek,
        organisation_id: employer,
        persona_id: self,
        position: employee.position,
        salary: money(employee.startSalary),
        start_date: employee.hireDate,
      },
    ],
    events,
    organisations,
    personas,
  };
}

function caseEvent(
  e: CareerEvent,
  id: string,
  self: string,
  refs: { provider?: string; examiner?: string; manager?: string; number: string },
): Events[string] {
  const base = { id, label: null, summary: null, participant_ids: [self] };
  switch (e.type) {
    case "contract_change":
      return {
        ...base,
        type: "contract_change",
        date: e.date,
        reason: e.reason,
        new_salary: e.newSalary !== undefined ? money(e.newSalary) : null,
        new_position: e.newPosition ?? null,
        new_contract_type: e.newContractType ?? null,
        new_hours: e.newHours ?? null,
      };
    case "training":
      if (!refs.provider) {
        throw new CaseBuildError(`${refs.number}: a training needs a provider; name one in the company profile.`);
      }
      return { ...base, type: "training", date: e.date, course: e.course, duration_days: e.durationDays, provider_id: refs.provider };
    case "appraisal":
      return {
        ...base,
        participant_ids: refs.manager ? [self, refs.manager] : [self],
        type: "appraisal",
        date: `${e.year}-06-30`,
        year: e.year,
        rating: e.rating,
        comment: e.comment ?? null,
      };
    case "medical_check":
      return {
        ...base,
        participant_ids: refs.examiner ? [self, refs.examiner] : [self],
        type: "medical_check",
        date: e.date,
        result: e.result,
      };
    case "absence":
      return { ...base, type: "absence", date: e.startDate, end_date: e.endDate ?? null };
    case "termination":
      return { ...base, type: "termination", date: e.date, reason: e.reason, notice_date: e.noticeDate ?? null };
  }
}
