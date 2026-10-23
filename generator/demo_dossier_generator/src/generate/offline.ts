import type { ISODate } from "../model/dates";
import { addDays, addMonths, iso, minDate, yearOf } from "../model/dates";
import type { Correction, Employee, Storyline } from "../model/dossier";
import { RATINGS } from "../model/dossier";
import type { Rng } from "../model/random";
import { createRng } from "../model/random";
import { newGenerationId } from "./config";
import { FIRST_NAMES, LAST_NAMES } from "./names";
import type { StorylinePlan } from "./normalize";
import { latestHire, normalizePersonas, normalizeStoryline, planStoryline } from "./normalize";
import type { DossierSet, GenerationConfig } from "./types";
import { COMMON_COURSES, DEPARTMENTS, department, salaryRange } from "./vocab";

/**
 * The "No AI" generator: random but plausible answers in exactly the shape the
 * AI is asked for. It runs through the same checks as AI answers. Use it to
 * test, to demo without a model, or to make large volumes quickly.
 */

function between(rng: Rng, from: ISODate, to: ISODate): ISODate {
  if (to <= from) return from;
  const days = Math.round((Date.parse(to) - Date.parse(from)) / 86_400_000);
  return addDays(from, rng.int(0, days));
}

export function offlinePersonasRaw(config: GenerationConfig, rng: Rng, count = config.employeeCount): unknown[] {
  const depts = config.departments.map((d) => department(d)).filter((d) => !!d);
  const list = depts.length ? depts : [DEPARTMENTS[0]];
  const out: Record<string, unknown>[] = [];
  for (let i = 0; i < count; i++) {
    const dept = list[i % list.length]!;
    const nonManager = dept.positions.filter((p) => !p.manager);
    const pos = rng.pick(nonManager);
    const partTime = rng.chance(config.scenario.partTimeShare);
    const hours = partTime ? rng.pick([24, 28, 32]) : rng.pick([36, 38, 40, 40]);
    const [lo, hi] = salaryRange(pos, hours);
    out.push({
      firstName: rng.pick(FIRST_NAMES),
      lastName: rng.pick(LAST_NAMES),
      department: dept.name,
      position: pos.title,
      isManager: false,
      hireDate: between(rng, config.earliestHire, latestHire(config)),
      contractType: rng.chance(config.scenario.temporaryShare) ? "Temporary" : "Permanent",
      hoursPerWeek: hours,
      startSalary: Math.round(rng.int(lo, hi) / 50) * 50,
    });
  }
  // Departments with 3 or more people get a manager: the longest-employed person.
  if (count === config.employeeCount) {
    for (const dept of list) {
      const members = out.filter((p) => p.department === dept!.name);
      if (members.length < 3) continue;
      const senior = [...members].sort((a, b) => String(a.hireDate).localeCompare(String(b.hireDate)))[0];
      const managerPos = dept!.positions.find((p) => p.manager)!;
      const [lo, hi] = salaryRange(managerPos, 40);
      Object.assign(senior, {
        isManager: true,
        position: managerPos.title,
        hoursPerWeek: 40,
        contractType: "Permanent",
        startSalary: Math.round(rng.int(lo, hi) / 50) * 50,
      });
    }
  }
  return out;
}

export function offlineStorylineRaw(plan: StorylinePlan, config: GenerationConfig, rng: Rng): unknown {
  const e = plan.employee;
  const events: Record<string, unknown>[] = [];
  let end = config.asOf;
  if (e.leaves) {
    const from = addMonths(e.hireDate, 8);
    const to = addMonths(config.asOf, -1);
    end = between(rng, from <= to ? from : to, to);
    events.push({
      type: "termination",
      date: end,
      reason: e.contractType === "Temporary" ? "End of temporary contract" : rng.pick(["Resignation", "Resignation", "Mutual agreement"]),
    });
  }

  const dept = department(e.department)!;
  let level = dept.positions.find((p) => p.title === e.position)?.level ?? 1;
  let salary = e.startSalary;
  for (let y = yearOf(e.hireDate) + 1; y <= yearOf(end); y++) {
    const date = iso(y, rng.pick([1, 4, 7]), 1);
    if (date > end) break;
    const promote = config.scenario.promotions && !e.isManager && level < 3 && rng.chance(0.15);
    if (promote) {
      const next = dept.positions.find((p) => p.level === level + 1 && !p.manager);
      if (next) {
        level = next.level;
        const [lo, hi] = salaryRange(next, e.hoursPerWeek);
        salary = Math.max(salary + 200, Math.round((lo + (hi - lo) * 0.3) / 50) * 50);
        events.push({ type: "contract_change", date, newPosition: next.title, newSalary: salary, reason: "Promotion" });
        continue;
      }
    }
    const current = dept.positions.find((p) => p.level === level && !!p.manager === e.isManager) ?? dept.positions[0];
    const cap = salaryRange(current, e.hoursPerWeek)[1];
    const raised = Math.min(cap, Math.round((salary * (1 + rng.int(2, 4) / 100)) / 50) * 50);
    if (raised > salary && rng.chance(0.55)) {
      salary = raised;
      events.push({ type: "contract_change", date, newSalary: salary, reason: "Annual salary review" });
    }
  }

  const courses = [...dept.courses, ...COMMON_COURSES];
  const trainings = rng.int(1, Math.max(1, Math.min(4, yearOf(end) - yearOf(e.hireDate) + 1)));
  const trainingFrom = addMonths(e.hireDate, 2);
  const trainingTo = minDate(end, config.asOf);
  for (let i = 0; i < trainings && trainingFrom < trainingTo; i++) {
    events.push({
      type: "training",
      date: between(rng, trainingFrom, trainingTo),
      course: rng.pick(courses),
      durationDays: rng.pick([1, 1, 2, 2, 3]),
    });
  }

  const absenceFrom = addMonths(e.hireDate, 3);
  const absenceTo = addDays(end, -20);
  for (let i = 0; i < plan.absencePeriods && absenceFrom < absenceTo; i++) {
    const start = between(rng, absenceFrom, absenceTo);
    events.push({ type: "absence", startDate: start, endDate: addDays(start, rng.int(3, 45)) });
  }

  const appraisals = plan.appraisalYears.map((year) => ({
    year,
    rating: rng.chance(0.08) ? RATINGS[0] : rng.chance(0.3) ? RATINGS[2] : RATINGS[1],
    comment: config.scenario.appraisalComments ? rng.pick(COMMENTS) : undefined,
  }));

  return { events, appraisals };
}

const COMMENTS = [
  "Reliable and well organised. Takes ownership of planning and keeps the team informed.",
  "Strong technical work this period. Could share knowledge with colleagues more often.",
  "Handles a high workload calmly. Next step is to take the lead in improvement projects.",
  "Good progress since the last review. Attention point: documenting decisions more consistently.",
  "Very helpful to colleagues and customers. Ready for more responsibility.",
  "Meets the agreed goals. Would benefit from a course to deepen specialist knowledge.",
];

/** Generates a complete dossier set without any model. */
export function generateOffline(config: GenerationConfig): DossierSet {
  const rng = createRng(config.seed);
  const personaRng = rng.fork("personas");
  const fill = (n: number) => offlinePersonasRaw(config, personaRng.fork("fill"), n);
  const { employees, corrections } = normalizePersonas(offlinePersonasRaw(config, personaRng), config, personaRng, fill);
  const { storylines, corrections: storyCorrections } = offlineStorylines(employees, config, rng.fork("storylines"));
  return {
    generationId: newGenerationId(config.seed),
    config,
    employees,
    storylines,
    corrections: [...corrections, ...storyCorrections],
    overrides: [],
    provenance: { personas: "No AI (built-in sample generator)", storylines: "No AI (built-in sample generator)" },
  };
}

export function offlineStorylines(
  employees: Employee[],
  config: GenerationConfig,
  rng: Rng,
): { storylines: Record<string, Storyline>; corrections: Correction[] } {
  const storylines: Record<string, Storyline> = {};
  const corrections: Correction[] = [];
  for (const e of employees) {
    const r = rng.fork(e.id);
    const plan = planStoryline(e, config, r);
    const raw = offlineStorylineRaw(plan, config, r);
    const result = normalizeStoryline(raw, plan, config, r);
    storylines[e.id] = result.storyline;
    corrections.push(...result.corrections);
  }
  return { storylines, corrections };
}
