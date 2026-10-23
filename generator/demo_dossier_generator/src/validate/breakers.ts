import { addDays } from "../model/dates";
import { netSalary, wageTax } from "../spec/rules";
import type { DossierPackage, DossierSet } from "../generate/types";

/**
 * "Break something" for the demo: each breaker plants one realistic mistake,
 * the kind a model makes when it writes documents without a shared fact base.
 * The validator should catch every one and block the export.
 */

export interface Breaker {
  id: string;
  label: string;
  /** What the validator should say, in words, for the presenter. */
  expect: string;
  apply(set: DossierSet, pkg: DossierPackage): string | null;
}

function middle<T>(items: T[]): T | undefined {
  return items[Math.floor(items.length / 2)];
}

export const BREAKERS: Breaker[] = [
  {
    id: "payslip",
    label: "Change one payslip amount",
    expect: "The payslip no longer matches the contract in force.",
    apply(_set, pkg) {
      const p = middle(pkg.documents.filter((d) => d.docType === "payslip"));
      if (!p) return null;
      const gross = Number(p.values.gross) + 250;
      p.values = { ...p.values, gross, tax: wageTax(gross), net: netSalary(gross) };
      return `${p.title} of employee ${p.employeeId} now shows EUR ${gross} gross.`;
    },
  },
  {
    id: "training",
    label: "Date a training before the start date",
    expect: "A document is dated before the employee was hired.",
    apply(set, pkg) {
      const t = pkg.documents.find((d) => d.docType === "training_certificate");
      if (!t) return null;
      const e = set.employees.find((x) => x.id === t.employeeId)!;
      const date = addDays(e.hireDate, -45);
      t.date = date;
      t.values = { ...t.values, completedOn: date };
      return `${t.title} of employee ${t.employeeId} is now dated ${date}, before the start date ${e.hireDate}.`;
    },
  },
  {
    id: "title",
    label: "Give two documents the same title",
    expect: "Content Server would refuse the second document.",
    apply(_set, pkg) {
      const byEmployee = new Map<string, typeof pkg.documents>();
      for (const d of pkg.documents) byEmployee.set(d.employeeId, [...(byEmployee.get(d.employeeId) ?? []), d]);
      for (const docs of byEmployee.values()) {
        const [a, b] = docs.filter((d) => d.docType !== "employment_contract").slice(-2);
        if (a && b) {
          b.title = a.title;
          return `"${b.fileName}" now has the same title as "${a.fileName}": ${a.title}.`;
        }
      }
      return null;
    },
  },
  {
    id: "group",
    label: "Use a group that does not exist",
    expect: "The import would fail: groups are never created by the import.",
    apply(_set, pkg) {
      const m = pkg.documents.find((d) => d.acl.some((a) => a.group));
      if (!m) return null;
      m.acl = m.acl.map((a) => (a.group ? { ...a, group: "HR Medical Team" } : a));
      return `${m.title} of employee ${m.employeeId} now grants access to "HR Medical Team".`;
    },
  },
];
