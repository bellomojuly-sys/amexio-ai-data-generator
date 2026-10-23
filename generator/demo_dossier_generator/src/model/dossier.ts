import type { ISODate } from "./dates";

/**
 * The dossier model: the facts every document is built from.
 *
 * The AI proposes personas and storylines; code assigns IDs, checks them and
 * turns them into documents. A document never invents a fact of its own: every
 * name, date and amount in a PDF or in import.xml is read from these objects.
 */

export type ContractType = "Permanent" | "Temporary";

export type Rating = "Below expectations" | "Meets expectations" | "Exceeds expectations";
export const RATINGS: readonly Rating[] = ["Below expectations", "Meets expectations", "Exceeds expectations"];

export type MedicalResult = "Fit for work" | "Fit for work with adjustments";
export const MEDICAL_RESULTS: readonly MedicalResult[] = ["Fit for work", "Fit for work with adjustments"];

export type TerminationReason = "Resignation" | "End of temporary contract" | "Mutual agreement" | "Retirement";
export const TERMINATION_REASONS: readonly TerminationReason[] = [
  "Resignation",
  "End of temporary contract",
  "Mutual agreement",
  "Retirement",
];

/** One person in the company; each employee gets one dossier (folder). */
export interface Employee {
  /** Six digits, assigned by code: 100101, 100102, ... */
  id: string;
  firstName: string;
  lastName: string;
  department: string;
  /** Position at hire. Later positions come from contract changes in the storyline. */
  position: string;
  hireDate: ISODate;
  contractType: ContractType;
  hoursPerWeek: number;
  /** Gross monthly salary at hire, whole euros. */
  startSalary: number;
  /** True for the head of a department. Managers have their own dossier too. */
  isManager: boolean;
  /** Employee ID of the manager when the manager is in this dataset. */
  managerId?: string;
  /** Free-text manager name when the manager is not in this dataset (as in AMEXIO's example). */
  managerName?: string;
  /** Code decides who leaves, so the dataset covers that branch; the AI picks the date and reason. */
  leaves: boolean;
}

export function fullName(e: Pick<Employee, "firstName" | "lastName">): string {
  return `${e.firstName} ${e.lastName}`.replace(/\s+/g, " ").trim();
}

export type CareerEvent =
  | {
      type: "contract_change";
      date: ISODate;
      reason: string;
      newSalary?: number;
      newPosition?: string;
      newContractType?: ContractType;
      newHours?: number;
    }
  | { type: "training"; date: ISODate; course: string; durationDays: number }
  | { type: "appraisal"; year: number; rating: Rating; comment?: string }
  | { type: "medical_check"; date: ISODate; result: MedicalResult }
  | { type: "absence"; startDate: ISODate; endDate?: ISODate }
  | { type: "termination"; date: ISODate; reason: TerminationReason; noticeDate?: ISODate };

export type CareerEventType = CareerEvent["type"];

export interface Storyline {
  employeeId: string;
  events: CareerEvent[];
}

/** Something code changed in what the AI returned, shown to the user for transparency. */
export interface Correction {
  step: "personas" | "storylines";
  employeeId?: string;
  message: string;
  /** "fix" = code changed something the AI proposed; "rule" = code added something a business rule requires. */
  kind?: "fix" | "rule";
}

export function eventDate(e: CareerEvent): ISODate {
  switch (e.type) {
    case "appraisal":
      return `${e.year}-06-30`;
    case "absence":
      return e.startDate;
    default:
      return e.date;
  }
}

export function sortEvents(events: CareerEvent[]): CareerEvent[] {
  return [...events].sort((a, b) => eventDate(a).localeCompare(eventDate(b)));
}
