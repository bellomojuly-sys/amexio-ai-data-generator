import { fullName } from "../../model/dossier";
import { monthYear, monthYearNl } from "../format";
import type { DocDraft, DocTypeSpec } from "../types";

/**
 * Contract amendment — EXTENSION, not in AMEXIO's example.
 * Records a raise, promotion, change of hours or a temporary contract made permanent.
 * Payslips after its effective date must show its salary.
 */
export const contractAmendment: DocTypeSpec = {
  id: "contract_amendment",
  documentType: "Contract Amendment",
  slug: "contract_amendment",
  origin: "extension",
  summary: "A change to the employment contract: raise, promotion, hours, or permanent contract.",
  occurs: "Once per contract change in the storyline.",
  titlePattern: "Contract Amendment {Month YYYY}",
  tags: ["contract", "amendment"],
  confidential: true,
  acl: [],
  fields: [
    { key: "effectiveDate", label: "Effective date", format: "date", origin: "storyline" },
    { key: "position", label: "Position", format: "text", origin: "storyline" },
    { key: "department", label: "Department", format: "text", origin: "persona" },
    { key: "contractType", label: "Contract type", format: "text", origin: "storyline" },
    { key: "hoursPerWeek", label: "Hours per week", format: "number", origin: "storyline" },
    {
      key: "salary",
      label: "Gross monthly salary",
      format: "eurGrouped",
      origin: "storyline",
      rule: "Contract format: '.' thousands separator, like the employment contract.",
    },
    { key: "reason", label: "Reason", format: "text", origin: "storyline" },
  ],
  dateField: "effectiveDate",
  rules: [
    "Shows the full contract terms in force from the effective date.",
    "Every payslip from the effective date until the next amendment shows this salary.",
  ],
  plan({ employee, timeline, asOf }) {
    const drafts: DocDraft[] = [];
    timeline.events.forEach((e, index) => {
      if (e.type !== "contract_change") return;
      if (e.date > asOf) return;
      const state = timeline.stateAt(e.date);
      drafts.push({
        date: e.date,
        title: `Contract Amendment ${monthYear(e.date)}`,
        titleNl: `Contractwijziging ${monthYearNl(e.date)}`,
        description: `Contract amendment of ${fullName(employee)}`,
        fileSuffix: e.date,
        sourceEvent: index,
        values: {
          effectiveDate: e.date,
          position: state.position,
          department: employee.department,
          contractType: state.contractType,
          hoursPerWeek: state.hoursPerWeek,
          salary: state.salary,
          reason: e.reason,
        },
      });
    });
    return drafts;
  },
};
