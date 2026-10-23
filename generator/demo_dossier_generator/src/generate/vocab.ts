/**
 * Allowed values for the fictional company "Acme Logistics B.V.", the company
 * in AMEXIO's example. The AI chooses from these lists; code rejects or clamps
 * anything outside them. The four example employees all fit these ranges.
 */

export interface PositionDef {
  title: string;
  /** Gross monthly salary range for full time (40 hours), whole euros. */
  salary: [number, number];
  level: 1 | 2 | 3 | 4;
  manager?: boolean;
}

export interface DepartmentDef {
  name: string;
  positions: PositionDef[];
  courses: string[];
}

export const DEPARTMENTS: readonly DepartmentDef[] = [
  {
    name: "IT",
    positions: [
      { title: "Junior Software Developer", salary: [3000, 3700], level: 1 },
      { title: "Software Developer", salary: [3800, 4900], level: 2 },
      { title: "Senior Software Developer", salary: [4800, 6000], level: 3 },
      { title: "IT Manager", salary: [5800, 7200], level: 4, manager: true },
    ],
    courses: ["Secure Coding Fundamentals", "Cloud Architecture Basics", "Agile Scrum Foundation", "Test Automation in Practice"],
  },
  {
    name: "Human Resources",
    positions: [
      { title: "HR Assistant", salary: [2700, 3300], level: 1 },
      { title: "HR Advisor", salary: [3500, 4400], level: 2 },
      { title: "Senior HR Advisor", salary: [4200, 5100], level: 3 },
      { title: "HR Manager", salary: [5200, 6500], level: 4, manager: true },
    ],
    courses: ["Employment Law Update", "Interviewing Skills", "GDPR for HR Professionals", "Absence Management Basics"],
  },
  {
    name: "Logistics",
    positions: [
      { title: "Warehouse Employee", salary: [2400, 2950], level: 1 },
      { title: "Warehouse Supervisor", salary: [3200, 3900], level: 2 },
      { title: "Logistics Planner", salary: [3300, 4200], level: 3 },
      { title: "Logistics Manager", salary: [4800, 6100], level: 4, manager: true },
    ],
    courses: ["Health & Safety Training", "Forklift Certification", "Lean Warehousing", "Dangerous Goods Awareness"],
  },
  {
    name: "Finance",
    positions: [
      { title: "Accountant", salary: [3200, 4100], level: 1 },
      { title: "Financial Controller", salary: [4600, 5700], level: 2 },
      { title: "Senior Financial Controller", salary: [5400, 6600], level: 3 },
      { title: "Finance Manager", salary: [6000, 7400], level: 4, manager: true },
    ],
    courses: ["IFRS Reporting Essentials", "Dutch Payroll Tax Update", "Excel for Finance Professionals", "Internal Controls Basics"],
  },
  {
    name: "Customer Service",
    positions: [
      { title: "Customer Service Agent", salary: [2500, 3000], level: 1 },
      { title: "Senior Customer Service Agent", salary: [2900, 3500], level: 2 },
      { title: "Team Lead Customer Service", salary: [3400, 4200], level: 3 },
      { title: "Customer Service Manager", salary: [4500, 5600], level: 4, manager: true },
    ],
    courses: ["Customer Communication", "Complaint Handling", "De-escalation Skills", "CRM Basics"],
  },
];

/** Company-wide courses any employee may take. */
export const COMMON_COURSES = ["BHV Emergency Response", "First Aid at Work", "Information Security Awareness"];

export const DEFAULT_DEPARTMENTS = ["IT", "Human Resources", "Logistics", "Finance"];

export function department(name: string): DepartmentDef | undefined {
  return DEPARTMENTS.find((d) => d.name.toLowerCase() === name.trim().toLowerCase());
}

export function position(dept: string, title: string): PositionDef | undefined {
  return department(dept)?.positions.find((p) => p.title.toLowerCase() === title.trim().toLowerCase());
}

/** Salary range scaled to part-time hours, rounded to 50 euros. */
export function salaryRange(pos: PositionDef, hoursPerWeek: number): [number, number] {
  const f = hoursPerWeek / 40;
  const round50 = (n: number) => Math.round((n * f) / 50) * 50;
  return [round50(pos.salary[0]), round50(pos.salary[1])];
}
