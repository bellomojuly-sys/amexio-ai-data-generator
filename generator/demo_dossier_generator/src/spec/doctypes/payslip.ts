import { iso, monthStart, parts } from "../../model/dates";
import { fullName } from "../../model/dossier";
import { monthYear, monthYearNl } from "../format";
import { netSalary, payDate, wageTax } from "../rules";
import type { DocDraft, DocTypeSpec } from "../types";

/** [3] Payslip — in AMEXIO's example. Monthly, paid on the 25th. */
export const payslip: DocTypeSpec = {
  id: "payslip",
  documentType: "Payslip",
  slug: "payslip",
  origin: "amexio",
  summary: "Monthly salary statement.",
  occurs: "Every month the employee is employed, paid on the 25th.",
  titlePattern: "Payslip {Month YYYY}",
  tags: ["payroll", "salary"],
  confidential: true,
  acl: [],
  fields: [
    { key: "period", label: "Period", format: "monthYear", origin: "rule" },
    { key: "paymentDate", label: "Payment date", format: "date", origin: "rule", rule: "The 25th of the period month." },
    {
      key: "gross",
      label: "Gross salary",
      format: "eurPlain",
      origin: "rule",
      rule: "Salary in the contract or latest amendment in force on the payment date. Payroll documents write amounts without a thousands separator (EUR 4350).",
    },
    { key: "tax", label: "Wage tax", format: "eurPlain", origin: "rule", rule: "37% of gross, rounded half to even." },
    { key: "net", label: "Net salary", format: "eurPlain", origin: "rule", rule: "Gross minus wage tax." },
  ],
  dateField: "paymentDate",
  rules: [
    "Gross salary equals the contract salary in force on the payment date.",
    "Wage tax = 37% of gross (rounded half to even); net = gross - tax.",
    "Payment date = 25th of the month = document date.",
  ],
  plan({ employee, timeline, asOf, windowStart }) {
    const drafts: DocDraft[] = [];
    const first = monthStart(windowStart > employee.hireDate ? windowStart : employee.hireDate);
    let { y, m } = parts(first);
    for (;;) {
      const date = payDate(y, m);
      if (date > asOf) break;
      if (timeline.endDate && date > timeline.endDate) break;
      if (date >= employee.hireDate) {
        const gross = timeline.stateAt(date).salary;
        drafts.push({
          date,
          title: `Payslip ${monthYear(date)}`,
          titleNl: `Loonstrook ${monthYearNl(date)}`,
          description: `Monthly payslip of ${fullName(employee)}`,
          fileSuffix: iso(y, m, 1).slice(0, 7),
          values: { period: date, paymentDate: date, gross, tax: wageTax(gross), net: netSalary(gross) },
        });
      }
      m += 1;
      if (m > 12) {
        m = 1;
        y += 1;
      }
    }
    return drafts;
  },
};
