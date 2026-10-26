import { yearOf } from "../../model/dates";
import { fullName } from "../../model/dossier";
import { annualStatementDate, netSalary, payDate, wageTax } from "../rules";
import type { DocDraft, DocTypeSpec } from "../types";

/**
 * Annual income statement (jaaropgave) — EXTENSION, not in AMEXIO's example.
 * Its totals must equal the sum of that year's payslips: a good cross-document check.
 */
export const annualIncomeStatement: DocTypeSpec = {
  id: "annual_income_statement",
  documentType: "Annual Income Statement",
  slug: "annual_income_statement",
  origin: "extension",
  summary: "Yearly totals of salary and wage tax (Dutch 'jaaropgave').",
  occurs: "Once per calendar year with pay, issued on 31 January of the next year.",
  titlePattern: "Annual Income Statement {YYYY}",
  tags: ["payroll", "tax"],
  confidential: true,
  acl: [],
  fields: [
    { key: "year", label: "Year", format: "number", origin: "rule" },
    { key: "employer", label: "Employer", format: "text", origin: "constant" },
    { key: "monthsPaid", label: "Months paid", format: "number", origin: "rule" },
    { key: "gross", label: "Total gross salary", format: "eurPlain", origin: "rule", rule: "Sum of that year's payslips." },
    { key: "tax", label: "Total wage tax", format: "eurPlain", origin: "rule", rule: "Sum of that year's payslips." },
    { key: "net", label: "Total net salary", format: "eurPlain", origin: "rule", rule: "Sum of that year's payslips." },
  ],
  rules: [
    "Totals = sum of gross, tax and net on that year's payslips.",
    "Issued on 31 January of the following year, also after the employee has left.",
  ],
  plan({ employee, timeline, company, asOf, windowStart }) {
    const drafts: DocDraft[] = [];
    const firstYear = Math.max(yearOf(employee.hireDate), yearOf(windowStart));
    for (let year = firstYear; ; year++) {
      const issued = annualStatementDate(year);
      if (issued > asOf) break;
      let gross = 0;
      let tax = 0;
      let net = 0;
      let months = 0;
      for (let m = 1; m <= 12; m++) {
        const pd = payDate(year, m);
        if (pd < employee.hireDate) continue;
        if (timeline.endDate && pd > timeline.endDate) continue;
        const g = timeline.stateAt(pd).salary;
        gross += g;
        tax += wageTax(g);
        net += netSalary(g);
        months++;
      }
      if (months === 0) {
        if (timeline.endDate && timeline.endDate < payDate(year, 1)) break;
        continue;
      }
      drafts.push({
        date: issued,
        title: `Annual Income Statement ${year}`,
        titleNl: `Jaaropgave ${year}`,
        description: `Annual income statement ${year} of ${fullName(employee)}`,
        fileSuffix: String(year),
        values: { year, employer: company.employerName, monthsPaid: months, gross, tax, net },
      });
    }
    return drafts;
  },
};
