import { describe, expect, it } from "vitest";
import type { CompletionRequest, ModelProvider } from "../src/ai/types";
import { cloneConfig, DEFAULT_CONFIG } from "../src/generate/config";
import { runPersonaStep, runStorylineStep } from "../src/generate/pipeline";
import { expandDossiers } from "../src/generate/expand";
import { validate } from "../src/validate/validate";
import { extractJson } from "../src/ai/json";

/**
 * The AI path, tested with a scripted fake model that makes typical mistakes.
 * Whatever the model returns, code must end up with documents that pass every check.
 */

function fakeModel(answers: ((prompt: string) => string)[]): ModelProvider & { prompts: string[] } {
  const prompts: string[] = [];
  let i = 0;
  return {
    id: "anthropic",
    label: "fake",
    describe: () => "fake model",
    prompts,
    async complete(req: CompletionRequest) {
      prompts.push(req.prompt);
      const answer = answers[Math.min(i++, answers.length - 1)](req.prompt);
      req.onText?.(answer);
      return answer;
    },
  };
}

const sloppyPersonas = JSON.stringify({
  employees: [
    { firstName: "Emre", lastName: "Şahin", department: "IT", position: "Software Developer", isManager: false, hireDate: "2018-04-01", contractType: "Permanent", hoursPerWeek: 40, startSalary: 4200 },
    { firstName: "Joyce", lastName: "Wałęsa", department: "Marketing", position: "Brand Manager", isManager: true, hireDate: "2016-02-01", contractType: "Permanent", hoursPerWeek: 40, startSalary: 9000 },
    { firstName: "Mark", lastName: "de Boer", department: "IT", position: "IT Manager", isManager: true, hireDate: "2015-06-01", contractType: "Permanent", hoursPerWeek: 40, startSalary: 6500 },
    { firstName: "Ilse", lastName: "Kok", department: "IT", position: "IT Manager", isManager: true, hireDate: "2019-06-01", contractType: "Permanent", hoursPerWeek: 40, startSalary: 6000 },
    { firstName: "Tom", lastName: "Bos", department: "Finance", position: "Accountant", isManager: false, hireDate: "2031-01-01", contractType: "temporary", hoursPerWeek: 12, startSalary: 100 },
    { firstName: "Tom", lastName: "Bos", department: "Finance", position: "Accountant", isManager: false, hireDate: "2020-01-01", contractType: "Permanent", hoursPerWeek: 32, startSalary: 3000 },
  ],
});

function sloppyStorylines(prompt: string): string {
  const ids = [...prompt.matchAll(/employeeId (\d{6})/g)].map((m) => m[1]);
  const storylines = ids.map((id) => ({
    employeeId: id,
    events: [
      { type: "contract_change", date: "2010-01-01", newSalary: 5000, reason: "Before hire" },
      { type: "contract_change", date: "2024-04-01", newSalary: 1500, reason: "Pay cut" },
      { type: "contract_change", date: "2025-01-01", newPosition: "IT Manager", newSalary: 9999, reason: "Promotion" },
      { type: "training", date: "2024-03-01", course: "Secure Coding Fundamentals", durationDays: 9 },
      { type: "training", date: "2024-05-01", course: "Agile Scrum Foundation", durationDays: 2 },
      { type: "training", date: "2024-06-01", course: "Third course in a year", durationDays: 2 },
      { type: "absence", startDate: "2023-02-01", endDate: "2023-01-01" },
      { type: "termination", date: "2024-03-15", reason: "Fired for fun" },
    ],
    appraisals: [
      { year: 2022, rating: "Excellent", comment: "Great year, 12 projects delivered." },
      { year: 2023, rating: "Meets expectations", comment: "Steady and dependable." },
    ],
  }));
  return "Here is the JSON:\n```json\n" + JSON.stringify({ storylines }) + "\n```";
}

describe("AI path with a sloppy model", () => {
  it("corrects every mistake and still passes validation", async () => {
    const config = cloneConfig(DEFAULT_CONFIG);
    config.employeeCount = 8;
    config.historyYears = 4;
    const model = fakeModel([() => sloppyPersonas, sloppyStorylines, sloppyStorylines]);

    const personas = await runPersonaStep(config, model);
    expect(personas.employees).toHaveLength(8);
    const names = personas.employees.map((e) => `${e.firstName} ${e.lastName}`);
    expect(names).toContain("Emre Sahin");
    expect(new Set(names).size).toBe(names.length);
    expect(personas.employees.filter((e) => e.department === "IT" && e.isManager)).toHaveLength(1);
    expect(personas.employees.every((e) => config.departments.includes(e.department))).toBe(true);
    expect(personas.corrections.length).toBeGreaterThan(4);

    const stories = await runStorylineStep(config, personas.employees, model);
    expect(model.prompts.length).toBe(1 + Math.ceil(8 / 5));
    const set = {
      generationId: "TEST",
      config,
      employees: personas.employees,
      storylines: stories.storylines,
      corrections: [...personas.corrections, ...stories.corrections],
      overrides: [],
      provenance: { personas: "fake", storylines: "fake" },
    };
    const pkg = expandDossiers(set);
    const report = validate(set, pkg);
    const errors = report.issues.filter((i) => i.severity === "error");
    expect(errors, errors.map((e) => e.message).join("\n")).toEqual([]);
    // Non-leavers lost their invented termination; comments with numbers were dropped.
    for (const e of personas.employees.filter((x) => !x.leaves)) {
      expect(stories.storylines[e.id].events.some((ev) => ev.type === "termination")).toBe(false);
    }
    expect(pkg.documents.some((d) => typeof d.values.comment === "string" && /\d/.test(d.values.comment))).toBe(false);
  });

  it("survives an answer that is not JSON", async () => {
    const config = cloneConfig(DEFAULT_CONFIG);
    config.employeeCount = 3;
    const model = fakeModel([() => sloppyPersonas, () => "Sorry, I cannot help with that."]);
    const personas = await runPersonaStep(config, model);
    const stories = await runStorylineStep(config, personas.employees, model);
    expect(Object.keys(stories.storylines)).toHaveLength(3);
    expect(stories.corrections.some((c) => c.message.includes("not valid JSON"))).toBe(true);
  });

  it("reads JSON wrapped in prose or a code fence", () => {
    expect(extractJson('Sure! {"a":1} Hope this helps.')).toEqual({ a: 1 });
    expect(extractJson("```json\n[1,2]\n```")).toEqual([1, 2]);
    expect(() => extractJson("no json here")).toThrow();
  });
});
