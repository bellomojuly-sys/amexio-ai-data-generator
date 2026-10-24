import type { Case, Document, Events } from "./generated/case";

/**
 * The case model's rules, checked in TypeScript before a case is saved or
 * rendered.
 *
 * The JSON Schema carries the shapes but not the rules between parts (see
 * "Rules the schema does not carry" in docs/HANDOFF_ROBIN.md). `load_case` in
 * case_model/ is the authority and runs on every committed demo case in CI
 * (case_model/test_demo_cases.py). This copy lets the demo catch the same
 * problems in the browser, where Python does not run, and list all of them
 * instead of stopping at the first. Keep it in step with
 * case_model/case_model.py: the tests feed both the same broken cases.
 */

type AnyEvent = Events[string];

const ID_PATTERNS = {
  persona: /^P[0-9]{3}$/,
  organisation: /^ORG-[0-9]{2}$/,
  event: /^EVT-[0-9]{3}$/,
  document: /^DOC-[0-9]{3}$/,
} as const;
const ID_EXAMPLES = { persona: "P001", organisation: "ORG-01", event: "EVT-001", document: "DOC-001" } as const;

const ROLES = ["employee", "manager", "hr_officer", "examiner"];
const CONTRACT_TYPES = ["Permanent", "Temporary"];
const RATINGS = ["Below expectations", "Meets expectations", "Exceeds expectations"];
const MEDICAL_RESULTS = ["Fit for work", "Fit for work with adjustments"];
const TERMINATION_REASONS = ["Resignation", "End of temporary contract", "Mutual agreement", "Retirement"];
export const DOCUMENT_TYPES = [
  "employment_contract",
  "payslip",
  "medical_check",
  "performance_appraisal",
  "training_certificate",
  "contract_amendment",
  "annual_income_statement",
  "absence_report",
  "termination_letter",
];
/** Documents that may have no event (D3a): they recur, they do not tell a story. */
export const RECURRING_DOCUMENT_TYPES = new Set(["payslip", "annual_income_statement"]);
const EVENT_TYPES = ["hire", "contract_change", "training", "appraisal", "medical_check", "absence", "termination"];

const ISO_DATE = /^[0-9]{4}-[0-9]{2}-[0-9]{2}$/;

function isDate(v: unknown): v is string {
  if (typeof v !== "string" || !ISO_DATE.test(v)) return false;
  const d = new Date(`${v}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === v;
}

/** Everything wrong with a case, in words. An empty list means load_case accepts it. */
export function checkCase(c: Case): string[] {
  const problems: string[] = [];
  const add = (m: string) => problems.push(m);
  const personas = c.personas ?? {};
  const organisations = c.organisations ?? {};
  const events = c.events ?? {};
  const documents = c.documents ?? {};
  const employments = c.employments ?? [];

  if (typeof c.case_number !== "string") add("case_number is missing.");
  if (!c.dossier || !/^[0-9]{6}$/.test(String(c.dossier.employee_number ?? ""))) {
    add(`Employee number must be six digits, got ${JSON.stringify(c.dossier?.employee_number)}.`);
  }

  // AX-011b — every part filed under a well-formed ID, and under its own ID.
  const collections: [Record<string, { id: string }>, string, keyof typeof ID_PATTERNS][] = [
    [personas, "Persona", "persona"],
    [organisations, "Organisation", "organisation"],
    [events, "Event", "event"],
    [documents, "Document", "document"],
  ];
  for (const [collection, label, kind] of collections) {
    for (const [key, part] of Object.entries(collection)) {
      if (!ID_PATTERNS[kind].test(key)) add(`Invalid ${kind} id ${JSON.stringify(key)}: expected the shape ${ID_EXAMPLES[kind]}.`);
      if (part?.id !== key) add(`${label} filed under ${JSON.stringify(key)} carries id ${JSON.stringify(part?.id)}.`);
    }
  }

  // Shapes and closed lists (pydantic checks these before any rule runs).
  for (const [pid, p] of Object.entries(personas)) {
    if (!p.name) add(`Persona ${pid} has no name.`);
    if (!ROLES.includes(p.role)) add(`Persona ${pid}: role ${JSON.stringify(p.role)} is not one of ${ROLES.join(", ")}.`);
    if (p.date_of_birth != null && !isDate(p.date_of_birth)) add(`Persona ${pid}: date_of_birth is not an ISO date.`);
    if (p.organisation_id && !(p.organisation_id in organisations)) {
      add(`Persona ${pid} points at unknown organisation ${JSON.stringify(p.organisation_id)}.`);
    }
  }
  for (const [oid, o] of Object.entries(organisations)) if (!o.name) add(`Organisation ${oid} has no name.`);

  employments.forEach((job, i) => {
    const where = `Employment ${i + 1}`;
    if (!(job.persona_id in personas)) add(`Employment points at unknown persona ${JSON.stringify(job.persona_id)}.`);
    if (!(job.organisation_id in organisations)) add(`Employment points at unknown organisation ${JSON.stringify(job.organisation_id)}.`);
    if (!isDate(job.start_date)) add(`${where}: start_date is not an ISO date.`);
    if (!CONTRACT_TYPES.includes(job.contract_type)) add(`${where}: contract_type ${JSON.stringify(job.contract_type)} is not one of ${CONTRACT_TYPES.join(", ")}.`);
    if (typeof job.hours !== "number") add(`${where}: hours must be a number.`);
    checkMoney(job.salary, `${where}: salary`, add);
  });

  for (const [eid, e] of Object.entries(events)) {
    checkEventShape(eid, e, add);
    for (const pid of e.participant_ids ?? []) {
      if (!(pid in personas)) add(`Event ${eid} references unknown persona ${JSON.stringify(pid)}.`);
    }
    if (e.type === "training" && !(e.provider_id in organisations)) {
      add(`Event ${eid} points at unknown training provider ${JSON.stringify(e.provider_id)}.`);
    }
  }

  checkStory(c, add);

  for (const [did, d] of Object.entries(documents)) checkDocument(c, did, d, add);
  return problems;
}

function checkMoney(m: { amount: string; currency: string } | null | undefined, where: string, add: (m: string) => void) {
  if (!m || typeof m !== "object") return add(`${where} is missing.`);
  if (!/^-?[0-9]+(\.[0-9]+)?$/.test(String(m.amount))) add(`${where}: amount must be a number, not ${JSON.stringify(m.amount)}.`);
  if (!/^[A-Z]{3}$/.test(String(m.currency))) add(`${where}: currency must be a 3-letter ISO 4217 code like 'EUR', got ${JSON.stringify(m.currency)}.`);
}

function checkEventShape(eid: string, e: AnyEvent, add: (m: string) => void) {
  if (!EVENT_TYPES.includes(e?.type)) return add(`Event ${eid}: unknown type ${JSON.stringify(e?.type)}.`);
  if (!isDate(e.date)) add(`Event ${eid}: date ${JSON.stringify(e.date)} is not an ISO date.`);
  if (!Array.isArray(e.participant_ids)) add(`Event ${eid}: participant_ids must be a list.`);
  switch (e.type) {
    case "contract_change":
      if (!e.reason) add(`Event ${eid}: a contract change needs a reason.`);
      if (e.new_salary != null) checkMoney(e.new_salary, `Event ${eid}: new_salary`, add);
      if (e.new_contract_type != null && !CONTRACT_TYPES.includes(e.new_contract_type)) add(`Event ${eid}: new_contract_type ${JSON.stringify(e.new_contract_type)} is not allowed.`);
      break;
    case "training":
      if (!e.course) add(`Event ${eid}: a training needs a course.`);
      if (!Number.isInteger(e.duration_days) || e.duration_days <= 0) add(`Event ${eid}: duration_days must be a whole number above 0.`);
      break;
    case "appraisal":
      if (!Number.isInteger(e.year)) add(`Event ${eid}: an appraisal needs a year.`);
      if (!RATINGS.includes(e.rating)) add(`Event ${eid}: rating ${JSON.stringify(e.rating)} is not one of ${RATINGS.join(", ")}.`);
      break;
    case "medical_check":
      if (!MEDICAL_RESULTS.includes(e.result)) add(`Event ${eid}: result ${JSON.stringify(e.result)} is not one of ${MEDICAL_RESULTS.join(", ")}.`);
      break;
    case "absence":
      if (e.end_date != null && !isDate(e.end_date)) add(`Event ${eid}: end_date is not an ISO date.`);
      break;
    case "termination":
      if (!TERMINATION_REASONS.includes(e.reason)) add(`Event ${eid}: reason ${JSON.stringify(e.reason)} is not one of ${TERMINATION_REASONS.join(", ")}.`);
      if (e.notice_date != null && !isDate(e.notice_date)) add(`Event ${eid}: notice_date is not an ISO date.`);
      break;
  }
}

/** BR-06 — rules between events that no single event can check. */
function checkStory(c: Case, add: (m: string) => void) {
  const events = Object.values(c.events ?? {});
  const hires = events.filter((e) => e.type === "hire");
  if (hires.length > 1) add(`A case has at most one hire event, found ${hires.length}.`);
  if (hires.length) {
    const hire = hires[0];
    const starts = (c.employments ?? []).filter((j) => hire.participant_ids.includes(j.persona_id)).map((j) => j.start_date);
    if (starts.length && !starts.includes(hire.date)) {
      add(`Hire event ${hire.id} is dated ${hire.date}, but the employment starts on ${[...starts].sort()[0]}.`);
    }
    for (const e of events) {
      if (e.date < hire.date) add(`Event ${e.id} (${e.type}, ${e.date}) happens before the hire on ${hire.date}.`);
    }
  }
  const terminations = events.filter((e) => e.type === "termination");
  if (terminations.length > 1) add(`A case has at most one termination event, found ${terminations.length}.`);
  if (terminations.length) {
    const lastDay = terminations[0].date;
    for (const e of events) {
      const ends = (e.type === "absence" && e.end_date) || e.date;
      if (ends > lastDay) add(`Event ${e.id} (${e.type}) runs to ${ends}, after the last working day ${lastDay}.`);
    }
  }
  for (const e of events) {
    if (e.type === "absence" && e.end_date && e.end_date < e.date) {
      add(`Absence ${e.id} ends on ${e.end_date}, before it starts on ${e.date}.`);
    }
  }
}

function checkDocument(c: Case, did: string, d: Document, add: (m: string) => void) {
  if (!DOCUMENT_TYPES.includes(d.type)) return add(`Document ${did}: unknown type ${JSON.stringify(d.type)}.`);
  if (d.event_id == null) {
    if (!RECURRING_DOCUMENT_TYPES.has(d.type)) {
      add(`Document ${did} (${d.type}) needs an event; only ${[...RECURRING_DOCUMENT_TYPES].sort().join(", ")} may have none.`);
    }
  } else if (!(d.event_id in (c.events ?? {}))) {
    add(`Document ${did} references unknown event ${JSON.stringify(d.event_id)}.`);
  }
  for (const pid of d.participant_ids ?? []) {
    if (!(pid in (c.personas ?? {}))) add(`Document ${did} references unknown persona ${JSON.stringify(pid)}.`);
  }
  const m = d.metadata;
  if (!m) return add(`Document ${did} has no metadata.`);
  if (!isDate(m.document_date)) add(`Document ${did}: document_date is not an ISO date.`);
  if (m.document_type !== d.type) add(`Document ${did} is a ${d.type} but its metadata says ${m.document_type}.`);
  if (m.employee_id !== c.dossier?.employee_number) {
    add(`Document ${did} belongs to employee ${m.employee_id}, not to this dossier (${c.dossier?.employee_number}).`);
  }
}
