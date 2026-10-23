import { iso, maxDate, yearOf } from "../../model/dates";
import { fullName } from "../../model/dossier";
import { appraisalPeriod } from "../rules";
import type { DocDraft, DocTypeSpec } from "../types";

/** [4] Performance appraisal — in AMEXIO's example. Yearly, mid-year review. */
export const performanceAppraisal: DocTypeSpec = {
  id: "performance_appraisal",
  documentType: "Performance Appraisal",
  slug: "performance_appraisal",
  origin: "amexio",
  summary: "Yearly review by the employee's manager.",
  occurs: "Once a year, on 30 June, for employees hired before 1 April of that year.",
  titlePattern: "Performance Appraisal {YYYY}",
  tags: ["appraisal", "review"],
  confidential: false,
  acl: [],
  fields: [
    {
      key: "reviewPeriod",
      label: "Review period",
      format: "dateRange",
      origin: "rule",
      rule: "01-01 to 30-06 of the year (as in AMEXIO's example), or from the start date if later.",
    },
    {
      key: "manager",
      label: "Manager",
      format: "text",
      origin: "persona",
      rule: "The department manager employed on the review date, otherwise the director.",
    },
    { key: "rating", label: "Overall rating", format: "text", origin: "storyline" },
    { key: "reviewDate", label: "Review date", format: "date", origin: "rule", rule: "Last day of the review period." },
    {
      key: "comment",
      label: "Manager comments",
      format: "text",
      origin: "ai-text",
      optional: true,
      rule: "Optional free text written by the AI. No names, dates or numbers.",
    },
  ],
  dateField: "reviewDate",
  rules: [
    "Review date = last day of the review period = document date.",
    "The manager must be employed on the review date and cannot be the employee.",
    "Rating is one of: Below expectations, Meets expectations, Exceeds expectations.",
  ],
  plan({ employee, timeline, asOf, windowStart, managerAt }) {
    const drafts: DocDraft[] = [];
    const firstYear = Math.max(yearOf(windowStart), yearOf(employee.hireDate));
    for (let year = firstYear; year <= yearOf(asOf); year++) {
      const period = appraisalPeriod(year);
      if (period.to > asOf) break;
      if (employee.hireDate > iso(year, 3, 31)) continue;
      if (!timeline.employedOn(period.to)) continue;
      const index = timeline.events.findIndex((e) => e.type === "appraisal" && e.year === year);
      const event = timeline.events[index];
      const appraisal = event?.type === "appraisal" ? event : undefined;
      const manager = managerAt(period.to);
      drafts.push({
        date: period.to,
        title: `Performance Appraisal ${year}`,
        titleNl: `Beoordeling ${year}`,
        description: `Yearly performance review of ${fullName(employee)}`,
        fileSuffix: String(year),
        sourceEvent: index >= 0 ? index : undefined,
        values: {
          reviewPeriod: { from: maxDate(period.from, employee.hireDate), to: period.to },
          manager: manager.label,
          rating: appraisal?.rating ?? "Meets expectations",
          reviewDate: period.to,
          comment: appraisal?.comment,
        },
        meta: manager.employeeId ? { managerId: manager.employeeId } : undefined,
      });
    }
    return drafts;
  },
};
