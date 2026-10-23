import { fullName } from "../../model/dossier";
import type { DocTypeSpec } from "../types";

/** [1] Employment contract — in AMEXIO's example. One per employee, dated on the start date. */
export const employmentContract: DocTypeSpec = {
  id: "employment_contract",
  documentType: "Employment Contract",
  slug: "employment_contract",
  origin: "amexio",
  summary: "The signed contract the employee was hired on.",
  occurs: "Once, on the start date.",
  titlePattern: "Employment Contract",
  tags: ["contract", "legal"],
  confidential: true,
  acl: [],
  fields: [
    { key: "employer", label: "Employer", format: "text", origin: "constant" },
    { key: "position", label: "Position", format: "text", origin: "persona" },
    { key: "department", label: "Department", format: "text", origin: "persona" },
    { key: "startDate", label: "Start date", format: "date", origin: "persona" },
    { key: "contractType", label: "Contract type", format: "text", origin: "persona" },
    { key: "hoursPerWeek", label: "Hours per week", format: "number", origin: "persona" },
    {
      key: "salary",
      label: "Gross monthly salary",
      format: "eurGrouped",
      origin: "persona",
      rule: "Contracts write amounts with a '.' thousands separator (EUR 4.350).",
    },
  ],
  dateField: "startDate",
  rules: [
    "Document date = start date = <created> = <modified> = Document Date attribute.",
    "Gross monthly salary = gross pay on every payslip until the first contract amendment.",
  ],
  plan({ employee, company }) {
    return [
      {
        date: employee.hireDate,
        title: "Employment Contract",
        titleNl: "Arbeidsovereenkomst",
        description: `Signed employment contract of ${fullName(employee)}`,
        fileSuffix: employee.hireDate,
        values: {
          employer: company.employerName,
          position: employee.position,
          department: employee.department,
          startDate: employee.hireDate,
          contractType: employee.contractType,
          hoursPerWeek: employee.hoursPerWeek,
          salary: employee.startSalary,
        },
      },
    ];
  },
};
