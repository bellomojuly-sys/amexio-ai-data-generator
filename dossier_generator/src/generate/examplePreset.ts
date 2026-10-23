import type { Employee, Storyline } from "../model/dossier";
import { AMEXIO_DOC_TYPES } from "../spec/doctypes";
import { cloneConfig, DEFAULT_CONFIG } from "./config";
import type { DossierSet, GenerationConfig } from "./types";

/**
 * AMEXIO's example package as generator input: the four employees, their
 * events, and the special cases the example shows once each. Generating from
 * this preset must reproduce the example's import.xml and PDF text exactly
 * (see tests/golden.test.ts). It needs no AI.
 */

export function exampleConfig(): GenerationConfig {
  const c = cloneConfig(DEFAULT_CONFIG);
  c.seed = 1;
  c.asOf = "2026-09-30";
  c.employeeCount = 4;
  c.departments = ["IT", "Human Resources", "Logistics", "Finance"];
  c.history = "latest";
  c.historyYears = 1;
  c.docTypes = [...AMEXIO_DOC_TYPES];
  c.scenario = {
    leaverShare: 0,
    temporaryShare: 0,
    partTimeShare: 0,
    absenceShare: 0,
    promotions: false,
    appraisalComments: false,
  };
  c.importOptions = { versionControlContracts: false, dutchTitles: false, action: "create", includeUpdateExample: false };
  c.target = { ...c.target, packageName: "mock-import-dossier" };
  return c;
}

const base = { contractType: "Permanent", hoursPerWeek: 40, isManager: false, leaves: false, managerName: "M. Bakker (fictional)" } as const;

export const EXAMPLE_EMPLOYEES: Employee[] = [
  { ...base, id: "100101", firstName: "Jan", lastName: "de Vries", department: "IT", position: "Software Developer", hireDate: "2021-03-01", startSalary: 4350 },
  { ...base, id: "100102", firstName: "Sanne", lastName: "Jansen", department: "Human Resources", position: "HR Advisor", hireDate: "2019-09-16", startSalary: 3900 },
  { ...base, id: "100103", firstName: "Mohamed", lastName: "El Amrani", department: "Logistics", position: "Warehouse Supervisor", hireDate: "2022-01-10", startSalary: 3450 },
  { ...base, id: "100104", firstName: "Lisa", lastName: "van den Berg", department: "Finance", position: "Financial Controller", hireDate: "2020-06-01", startSalary: 5100 },
];

const examStory = (employeeId: string, course: string, rating: "Meets expectations" | "Exceeds expectations"): Storyline => ({
  employeeId,
  events: [
    { type: "training", date: "2026-02-20", course, durationDays: 2 },
    { type: "medical_check", date: "2026-04-14", result: "Fit for work" },
    { type: "appraisal", year: 2026, rating },
  ],
});

export function examplePreset(): DossierSet {
  return {
    generationId: "AMEXIO-EXAMPLE",
    config: exampleConfig(),
    employees: EXAMPLE_EMPLOYEES.map((e) => ({ ...e })),
    storylines: {
      "100101": examStory("100101", "Secure Coding Fundamentals", "Exceeds expectations"),
      "100102": examStory("100102", "Employment Law Update", "Meets expectations"),
      "100103": examStory("100103", "Health & Safety Training", "Meets expectations"),
      "100104": examStory("100104", "IFRS Reporting Essentials", "Exceeds expectations"),
    },
    corrections: [],
    // The special cases from the example, each shown once:
    overrides: [
      // Version control: the contract of 100101 is stored as major version 1.0
      { employeeId: "100101", docType: "employment_contract", set: { versionControl: "MAJOR" } },
      // Multilingual: the payslip of 100102 also has a Dutch title
      { employeeId: "100102", docType: "payslip", set: { extraTitles: { nl: "Loonstrook september 2026" } } },
      // CDATA: this title contains '&'
      { employeeId: "100103", docType: "training_certificate", set: { title: "Training Certificate Health & Safety" } },
      // sync instead of create
      { employeeId: "100104", docType: "performance_appraisal", set: { action: "sync" } },
    ],
    updates: [
      {
        location: "Enterprise:HR Dossiers:100101 Jan de Vries",
        title: "Payslip September 2026",
        description: "Monthly payslip of Jan de Vries (checked by payroll)",
      },
    ],
    provenance: { personas: "AMEXIO example (fixed data)", storylines: "AMEXIO example (fixed data)" },
  };
}
