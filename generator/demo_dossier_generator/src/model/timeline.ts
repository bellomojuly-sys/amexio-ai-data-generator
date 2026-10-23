import type { ISODate } from "./dates";
import type { CareerEvent, ContractType, Employee, Storyline } from "./dossier";
import { sortEvents } from "./dossier";

/**
 * Answers "what was true for this employee on this date?" by replaying the
 * storyline's contract changes on top of the hire facts. Payslips, amendments
 * and annual statements all read from here, which is what keeps a payslip in
 * line with the contract that was in force that month.
 */

export interface EmploymentState {
  position: string;
  salary: number;
  contractType: ContractType;
  hoursPerWeek: number;
}

export interface Timeline {
  employee: Employee;
  events: CareerEvent[];
  /** Last working day, when the employee leaves. */
  endDate?: ISODate;
  stateAt(date: ISODate): EmploymentState;
  /** True when the employee works for the company on that date. */
  employedOn(date: ISODate): boolean;
  /** Contract changes, in date order. */
  changes: Extract<CareerEvent, { type: "contract_change" }>[];
}

export function buildTimeline(employee: Employee, storyline: Storyline | undefined): Timeline {
  const events = sortEvents(storyline?.events ?? []);
  const changes = events.filter(
    (e): e is Extract<CareerEvent, { type: "contract_change" }> => e.type === "contract_change",
  );
  const termination = events.find((e) => e.type === "termination") as
    | Extract<CareerEvent, { type: "termination" }>
    | undefined;

  const stateAt = (date: ISODate): EmploymentState => {
    const s: EmploymentState = {
      position: employee.position,
      salary: employee.startSalary,
      contractType: employee.contractType,
      hoursPerWeek: employee.hoursPerWeek,
    };
    for (const c of changes) {
      if (c.date > date) break;
      if (c.newPosition) s.position = c.newPosition;
      if (c.newSalary) s.salary = c.newSalary;
      if (c.newContractType) s.contractType = c.newContractType;
      if (c.newHours) s.hoursPerWeek = c.newHours;
    }
    return s;
  };

  return {
    employee,
    events,
    endDate: termination?.date,
    stateAt,
    employedOn: (date) => date >= employee.hireDate && (!termination || date <= termination.date),
    changes,
  };
}
