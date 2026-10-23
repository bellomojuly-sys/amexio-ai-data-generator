import type { ISODate } from "../model/dates";
import { addDays, addMonths, addYears, isISODate, iso, minDate, monthEnd, yearOf } from "../model/dates";
import type { CareerEvent, ContractType, Correction, Employee, Rating, Storyline, TerminationReason } from "../model/dossier";
import { fullName, MEDICAL_RESULTS, RATINGS, sortEvents, TERMINATION_REASONS } from "../model/dossier";
import type { Rng } from "../model/random";
import { nextMedicalCheck } from "../spec/rules";
import { nonWinAnsiChars } from "../export/winansi";
import type { GenerationConfig } from "./types";
import { DEPARTMENTS, department, position, salaryRange } from "./vocab";

/**
 * Code checks every AI answer before anyone sees it. Anything outside the
 * allowed values is corrected, and each correction is recorded so the user can
 * see what the AI got wrong. The "No AI" generator goes through the same code.
 */

// ---------- small helpers ----------

const TRANSLIT: Record<string, string> = { ł: "l", Ł: "L", ı: "i", İ: "I", đ: "d", Đ: "D", ğ: "g", Ğ: "G", ş: "s", Ş: "S", ț: "t", ș: "s" };

/** Keeps Latin-1 letters (é, ö, ë are fine) and replaces only what the PDF font cannot print. */
export function printable(text: string): string {
  let out = "";
  for (const ch of text) {
    if (nonWinAnsiChars(ch).length === 0) {
      out += ch;
      continue;
    }
    const mapped = TRANSLIT[ch] ?? ch.normalize("NFD").replace(/[̀-ͯ]/g, "");
    out += nonWinAnsiChars(mapped).length === 0 ? mapped : "";
  }
  return out;
}

function cleanText(value: unknown, maxLength: number): string {
  if (typeof value !== "string") return "";
  return printable(value.replace(/\s+/g, " ").trim()).slice(0, maxLength).trim();
}

function asNumber(value: unknown): number | undefined {
  const n = typeof value === "string" ? Number(value.replace(/[^\d.-]/g, "")) : Number(value);
  return Number.isFinite(n) ? n : undefined;
}

function clamp(n: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, n));
}

function asList(raw: unknown, key: string): unknown[] {
  if (Array.isArray(raw)) return raw;
  if (raw && typeof raw === "object" && Array.isArray((raw as Record<string, unknown>)[key])) {
    return (raw as Record<string, unknown[]>)[key];
  }
  return [];
}

function obj(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" ? (v as Record<string, unknown>) : {};
}

function randomDate(rng: Rng, from: ISODate, to: ISODate): ISODate {
  if (to <= from) return from;
  const span = Math.max(0, Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000));
  return addDays(from, rng.int(0, span));
}

// ---------- personas ----------

export function latestHire(config: GenerationConfig): ISODate {
  return addMonths(config.asOf, -3);
}

export interface PersonaResult {
  employees: Employee[];
  corrections: Correction[];
}

export function normalizePersonas(
  raw: unknown,
  config: GenerationConfig,
  rng: Rng,
  fill: (count: number) => unknown[],
): PersonaResult {
  const corrections: Correction[] = [];
  const note = (message: string) => corrections.push({ step: "personas", message });
  const depts = config.departments.map((d) => department(d)).filter((d): d is NonNullable<typeof d> => !!d);
  if (depts.length === 0) depts.push(DEPARTMENTS[0]);

  let items = asList(raw, "employees").slice(0, config.employeeCount);
  if (items.length < config.employeeCount) {
    const missing = config.employeeCount - items.length;
    if (items.length > 0 || raw !== undefined) note(`The AI returned ${items.length} of ${config.employeeCount} employees; code added ${missing}.`);
    items = [...items, ...fill(missing)];
  }

  const drafts = items.map((item, index) => {
    const r = obj(item);
    let firstName = cleanText(r.firstName, 30);
    let lastName = cleanText(r.lastName, 40);
    if (!firstName || !lastName) {
      note(`Employee ${index + 1} had no usable name; code picked one.`);
      const filler = obj(fill(1)[0]);
      firstName = firstName || String(filler.firstName);
      lastName = lastName || String(filler.lastName);
    }
    const rawName = `${String(r.firstName ?? "")} ${String(r.lastName ?? "")}`.trim();
    if (rawName && rawName !== `${firstName} ${lastName}` && nonWinAnsiChars(rawName).length > 0) {
      note(`"${rawName}" has characters the PDF font cannot print; written as "${firstName} ${lastName}".`);
    }

    let dept = department(String(r.department ?? ""));
    if (!dept || !depts.includes(dept)) {
      const assigned = depts[index % depts.length];
      note(`${firstName} ${lastName}: department "${String(r.department ?? "")}" is not in the configuration; moved to ${assigned.name}.`);
      dept = assigned;
    }

    let pos = position(dept.name, String(r.position ?? ""));
    if (!pos) {
      pos = dept.positions[1] ?? dept.positions[0];
      note(`${firstName} ${lastName}: position "${String(r.position ?? "")}" does not exist in ${dept.name}; set to ${pos.title}.`);
    }

    let hireDate = typeof r.hireDate === "string" && isISODate(r.hireDate) ? r.hireDate : "";
    const hi = latestHire(config);
    if (!hireDate || hireDate < config.earliestHire || hireDate > hi) {
      const fixed = hireDate ? (hireDate < config.earliestHire ? config.earliestHire : hi) : randomDate(rng, config.earliestHire, hi);
      note(`${firstName} ${lastName}: hire date "${String(r.hireDate ?? "")}" is outside ${config.earliestHire} to ${hi}; set to ${fixed}.`);
      hireDate = fixed;
    }

    const contractType: ContractType = String(r.contractType).toLowerCase().startsWith("temp") ? "Temporary" : "Permanent";
    let hours = Math.round(asNumber(r.hoursPerWeek) ?? 40);
    if (hours < 16 || hours > 40) {
      note(`${firstName} ${lastName}: ${hours} hours per week is outside 16-40; set to ${clamp(hours, 16, 40)}.`);
      hours = clamp(hours, 16, 40);
    }

    return { firstName, lastName, dept, pos, hireDate, contractType, hours, rawSalary: asNumber(r.startSalary), isManager: r.isManager === true || !!pos.manager };
  });

  // One manager per department with 3 or more people; nobody else gets a manager title.
  for (const dept of depts) {
    const members = drafts.filter((d) => d.dept === dept);
    const managers = members.filter((d) => d.isManager);
    const managerPos = dept.positions.find((p) => p.manager)!;
    const seniorPos = [...dept.positions].reverse().find((p) => !p.manager)!;
    if (members.length >= 3 && managers.length === 0) {
      const senior = [...members].sort((a, b) => a.hireDate.localeCompare(b.hireDate))[0];
      senior.isManager = true;
      senior.pos = managerPos;
      note(`${dept.name} has ${members.length} people but no manager; ${senior.firstName} ${senior.lastName} (longest employed) became ${managerPos.title}.`);
    }
    const all = members.filter((d) => d.isManager).sort((a, b) => a.hireDate.localeCompare(b.hireDate));
    for (const extra of all.slice(1)) {
      extra.isManager = false;
      extra.pos = seniorPos;
      note(`${dept.name} had more than one manager; ${extra.firstName} ${extra.lastName} became ${seniorPos.title}.`);
    }
    for (const d of members) {
      if (!d.isManager && d.pos.manager) d.pos = seniorPos;
      if (d.isManager) {
        d.pos = managerPos;
        d.contractType = "Permanent";
      }
    }
  }

  // Unique names.
  const seen = new Set<string>();
  for (const d of drafts) {
    let name = `${d.firstName} ${d.lastName}`.toLowerCase();
    if (seen.has(name)) {
      const filler = obj(fill(1)[0]);
      note(`Two employees were both called ${d.firstName} ${d.lastName}; the second became ${d.firstName} ${String(filler.lastName)}.`);
      d.lastName = String(filler.lastName);
      name = `${d.firstName} ${d.lastName}`.toLowerCase();
    }
    seen.add(name);
  }

  // Personnel numbers follow hire order.
  drafts.sort((a, b) => a.hireDate.localeCompare(b.hireDate));

  const employees: Employee[] = drafts.map((d, i) => {
    const [lo, hi] = salaryRange(d.pos, d.hours);
    let salary = Math.round(d.rawSalary ?? (lo + hi) / 2);
    if (salary < lo || salary > hi) {
      const fixed = Math.round(clamp(salary, lo, hi) / 50) * 50;
      note(`${d.firstName} ${d.lastName}: start salary EUR ${salary} is outside EUR ${lo}-${hi} for ${d.pos.title} at ${d.hours} hours; set to EUR ${fixed}.`);
      salary = fixed;
    }
    return {
      id: String(100101 + i),
      firstName: d.firstName,
      lastName: d.lastName,
      department: d.dept.name,
      position: d.pos.title,
      hireDate: d.hireDate,
      contractType: d.contractType,
      hoursPerWeek: d.hours,
      startSalary: salary,
      isManager: d.isManager,
      leaves: false,
    };
  });

  for (const e of employees) {
    if (e.isManager) continue;
    const manager = employees.find((m) => m.isManager && m.department === e.department);
    if (manager) e.managerId = manager.id;
  }

  // Scenario coverage is decided by code, not left to chance in the AI's answer.
  const candidates = rng.shuffle(employees.filter((e) => !e.isManager && e.hireDate <= addYears(config.asOf, -1)));
  const leaverCount = Math.round(config.scenario.leaverShare * employees.length);
  for (const e of candidates.slice(0, leaverCount)) e.leaves = true;

  return { employees, corrections };
}

// ---------- storylines ----------

/** Years in which the employee gets an appraisal (same rule as the appraisal document type). */
export function appraisalYears(e: Employee, end: ISODate, asOf: ISODate): number[] {
  const years: number[] = [];
  for (let y = yearOf(e.hireDate); y <= yearOf(asOf); y++) {
    const review = iso(y, 6, 30);
    if (review > asOf || review > end) break;
    if (e.hireDate > iso(y, 3, 31)) continue;
    years.push(y);
  }
  return years;
}

/** Appraisal years that end up in documents: the history window, or only the latest in "latest" mode. */
export function appraisalYearsInScope(e: Employee, end: ISODate, config: GenerationConfig): number[] {
  const all = appraisalYears(e, end, config.asOf);
  if (config.history === "latest") return all.slice(-1);
  const from = yearOf(addYears(config.asOf, -config.historyYears));
  return all.filter((y) => y >= from);
}

export interface StorylinePlan {
  employee: Employee;
  /** Last possible date for events: as-of date, or the last working day for leavers (decided by the AI within limits). */
  latestEnd: ISODate;
  absencePeriods: number;
  appraisalYears: number[];
}

export function planStoryline(e: Employee, config: GenerationConfig, rng: Rng): StorylinePlan {
  const absent = rng.chance(config.scenario.absenceShare);
  return {
    employee: e,
    latestEnd: config.asOf,
    absencePeriods: absent ? rng.int(1, 2) : 0,
    appraisalYears: appraisalYearsInScope(e, config.asOf, config),
  };
}

export function normalizeStoryline(
  raw: unknown,
  plan: StorylinePlan,
  config: GenerationConfig,
  rng: Rng,
): { storyline: Storyline; corrections: Correction[] } {
  const e = plan.employee;
  const name = fullName(e);
  const corrections: Correction[] = [];
  const note = (message: string, kind: "fix" | "rule" = "fix") =>
    corrections.push({ step: "storylines", employeeId: e.id, message: `${name}: ${message}`, kind });
  const r = obj(raw);
  const rawEvents = asList(r.events ?? raw, "events").map(obj);
  const events: CareerEvent[] = [];

  // Termination first: it sets the end of everything else.
  let end = config.asOf;
  const rawTermination = rawEvents.find((x) => x.type === "termination");
  const earliestLeave = monthEnd(addMonths(e.hireDate, 6));
  if (e.leaves) {
    let date = typeof rawTermination?.date === "string" && isISODate(rawTermination.date) ? monthEnd(rawTermination.date) : "";
    if (!date || date < earliestLeave || date > config.asOf) {
      const fixed = monthEnd(randomDate(rng, earliestLeave, addMonths(config.asOf, -1)));
      if (rawTermination) note(`last working day "${String(rawTermination.date ?? "")}" was not usable; set to ${fixed}.`);
      else note(`was chosen to leave but the AI gave no leaving date; set to ${fixed}.`);
      date = minDate(fixed, monthEnd(addMonths(config.asOf, -1)));
    }
    let reason = TERMINATION_REASONS.find((t) => t.toLowerCase() === String(rawTermination?.reason ?? "").toLowerCase());
    if (!reason) {
      reason = (e.contractType === "Temporary" ? "End of temporary contract" : "Resignation") as TerminationReason;
      if (rawTermination) note(`leaving reason "${String(rawTermination.reason ?? "")}" is not allowed; set to ${reason}.`);
    }
    end = date;
    events.push({ type: "termination", date, reason });
  } else if (rawTermination) {
    note("the AI added a termination, but this employee stays; removed.");
  }

  const inRange = (d: unknown): d is ISODate => typeof d === "string" && isISODate(d) && d > e.hireDate && d <= end;

  // Contract changes
  const dept = department(e.department)!;
  let current = { position: e.position, salary: e.startSalary, contractType: e.contractType, hours: e.hoursPerWeek };
  const changes = rawEvents
    .filter((x) => x.type === "contract_change")
    .sort((a, b) => String(a.date).localeCompare(String(b.date)));
  for (const c of changes) {
    if (!inRange(c.date)) {
      note(`contract change on "${String(c.date ?? "")}" is outside the employment period; removed.`);
      continue;
    }
    const ev: Extract<CareerEvent, { type: "contract_change" }> = {
      type: "contract_change",
      date: c.date,
      reason: cleanText(c.reason, 80) || "Annual salary review",
    };
    let pos = position(e.department, String(c.newPosition ?? "")) ?? undefined;
    if (c.newPosition && !pos) note(`position "${String(c.newPosition)}" does not exist in ${e.department}; promotion removed.`);
    if (pos && !config.scenario.promotions) pos = undefined;
    const currentLevel = position(e.department, current.position)?.level ?? 1;
    if (pos && (pos.level <= currentLevel || (pos.manager && !e.isManager))) {
      if (pos.title !== current.position) note(`"${pos.title}" is not a step up from ${current.position}; promotion removed.`);
      pos = undefined;
    }
    if (pos) ev.newPosition = pos.title;
    const newType = String(c.newContractType ?? "");
    if (newType.toLowerCase().startsWith("perm") && current.contractType === "Temporary") ev.newContractType = "Permanent";
    const hours = asNumber(c.newHours);
    if (hours && Math.round(hours) !== current.hours && hours >= 16 && hours <= 40) ev.newHours = Math.round(hours);

    const effectivePos = position(e.department, ev.newPosition ?? current.position) ?? dept.positions[0];
    const [lo, hi] = salaryRange(effectivePos, ev.newHours ?? current.hours);
    const salary = asNumber(c.newSalary);
    if (salary !== undefined && Math.round(salary) !== current.salary) {
      let s = Math.round(salary);
      if (s < current.salary && !ev.newHours) {
        note(`salary would drop from EUR ${current.salary} to EUR ${s} without a change in hours; change removed.`);
        s = current.salary;
      }
      if (s < lo || s > hi) {
        const fixed = Math.round(clamp(s, lo, hi) / 50) * 50;
        if (fixed !== s) note(`new salary EUR ${s} is outside EUR ${lo}-${hi} for ${effectivePos.title}; set to EUR ${fixed}.`);
        s = fixed;
      }
      if (s !== current.salary) ev.newSalary = s;
    } else if (ev.newPosition || ev.newHours) {
      const s = Math.round(clamp(current.salary, lo, hi) / 50) * 50;
      if (s !== current.salary) ev.newSalary = s;
    }
    if (!ev.newSalary && !ev.newPosition && !ev.newContractType && !ev.newHours) continue;
    events.push(ev);
    current = {
      position: ev.newPosition ?? current.position,
      salary: ev.newSalary ?? current.salary,
      contractType: ev.newContractType ?? current.contractType,
      hours: ev.newHours ?? current.hours,
    };
  }

  // A temporary contract becomes permanent after a year, unless the person leaves at its end.
  const leavesAtTempEnd = events.some((x) => x.type === "termination" && x.reason === "End of temporary contract");
  if (e.contractType === "Temporary" && current.contractType === "Temporary" && !leavesAtTempEnd) {
    const date = addYears(e.hireDate, 1);
    if (date <= end) {
      events.push({ type: "contract_change", date, reason: "Temporary contract made permanent", newContractType: "Permanent" });
      note(`temporary contract made permanent on ${date} (rule: after one year).`, "rule");
    }
  }

  // Trainings: at most two per year.
  const perYear = new Map<number, number>();
  for (const t of rawEvents.filter((x) => x.type === "training")) {
    if (!inRange(t.date)) {
      note(`training on "${String(t.date ?? "")}" is outside the employment period; removed.`);
      continue;
    }
    const course = cleanText(t.course, 60);
    if (!course) continue;
    const y = yearOf(t.date);
    if ((perYear.get(y) ?? 0) >= 2) {
      note(`more than two trainings in ${y}; "${course}" removed.`);
      continue;
    }
    perYear.set(y, (perYear.get(y) ?? 0) + 1);
    events.push({ type: "training", date: t.date, course, durationDays: clamp(Math.round(asNumber(t.durationDays) ?? 2), 1, 5) });
  }

  // Absences: dates only, never a cause.
  const absences = rawEvents.filter((x) => x.type === "absence").slice(0, Math.max(plan.absencePeriods, 0));
  if (plan.absencePeriods === 0 && rawEvents.some((x) => x.type === "absence")) note("the AI added sick leave, but none was planned; removed.");
  let lastAbsenceEnd = e.hireDate;
  for (const a of absences.sort((x, y) => String(x.startDate).localeCompare(String(y.startDate)))) {
    if (!inRange(a.startDate) || a.startDate <= lastAbsenceEnd) {
      note(`sick leave starting "${String(a.startDate ?? "")}" is not usable; removed.`);
      continue;
    }
    let endDate = typeof a.endDate === "string" && isISODate(a.endDate) ? a.endDate : undefined;
    if (endDate && (endDate < a.startDate || endDate > end)) {
      note(`sick leave end "${endDate}" is not possible; set to ${minDate(addDays(a.startDate, 14), end)}.`);
      endDate = minDate(addDays(a.startDate, 14), end);
    }
    if (!endDate && (e.leaves || a.startDate < addMonths(config.asOf, -6))) endDate = minDate(addDays(a.startDate, 10), end);
    events.push({ type: "absence", startDate: a.startDate, endDate });
    lastAbsenceEnd = endDate ?? config.asOf;
  }

  // Appraisals: one rating for every year that needs one.
  const years = appraisalYearsInScope(e, end, config);
  const rawAppraisals = asList(r.appraisals, "appraisals").map(obj);
  for (const y of years) {
    const a = rawAppraisals.find((x) => Number(x.year) === y);
    let rating = RATINGS.find((v) => v.toLowerCase() === String(a?.rating ?? "").toLowerCase()) as Rating | undefined;
    if (!rating) {
      rating = "Meets expectations";
      note(`no usable rating for ${y}; set to Meets expectations.`);
    }
    let comment: string | undefined;
    if (config.scenario.appraisalComments && a?.comment) {
      comment = cleanText(a.comment, 280);
      if (/\d/.test(comment)) {
        note(`appraisal comment for ${y} contained numbers or dates; removed (facts come from code only).`);
        comment = undefined;
      }
    }
    events.push({ type: "appraisal", year: y, rating, ...(comment ? { comment } : {}) });
  }

  // Medical checks: scheduled by code. First check within 4 months of hire, then every 2 years.
  let check = addDays(e.hireDate, rng.int(30, 120));
  while (check <= minDate(end, config.asOf)) {
    const result = rng.chance(0.1) ? MEDICAL_RESULTS[1] : MEDICAL_RESULTS[0];
    events.push({ type: "medical_check", date: check, result });
    check = nextMedicalCheck(check);
  }

  return { storyline: { employeeId: e.id, events: sortEvents(events) }, corrections };
}
