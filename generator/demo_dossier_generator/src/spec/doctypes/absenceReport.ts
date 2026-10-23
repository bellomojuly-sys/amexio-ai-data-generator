import { fullName } from "../../model/dossier";
import { monthYear, monthYearNl } from "../format";
import { MEDICAL_ACL } from "../target";
import type { DocDraft, DocTypeSpec } from "../types";

/**
 * Absence report (sick leave registration) — EXTENSION, not in AMEXIO's example.
 * Dates only, never a cause or diagnosis. Same access rules as medical checks.
 */
export const absenceReport: DocTypeSpec = {
  id: "absence_report",
  documentType: "Absence Report",
  slug: "absence_report",
  origin: "extension",
  summary: "Registration of a sick-leave period: dates only, no cause or diagnosis.",
  occurs: "Once per absence period in the storyline.",
  titlePattern: "Absence Report {Month YYYY}",
  tags: ["absence", "health"],
  confidential: true,
  acl: MEDICAL_ACL,
  fields: [
    { key: "absenceType", label: "Absence type", format: "text", origin: "constant" },
    { key: "firstDay", label: "First day of absence", format: "date", origin: "storyline" },
    {
      key: "returnDate",
      label: "Return to work",
      format: "date",
      origin: "storyline",
      rule: "'Not yet returned' when the absence is still running on the as-of date.",
    },
    { key: "reportedTo", label: "Reported to", format: "text", origin: "constant" },
  ],
  dateField: "firstDay",
  rules: [
    "First day of absence = document date.",
    "Return date is after the first day and not after the last working day.",
    "No cause or diagnosis is ever recorded. Access: HR Medical group only.",
  ],
  plan({ employee, timeline, company, asOf, windowStart }) {
    const drafts: DocDraft[] = [];
    timeline.events.forEach((e, index) => {
      if (e.type !== "absence") return;
      if (e.startDate > asOf || e.startDate < windowStart) return;
      const returned = e.endDate && e.endDate <= asOf ? e.endDate : "Not yet returned";
      drafts.push({
        date: e.startDate,
        title: `Absence Report ${monthYear(e.startDate)}`,
        titleNl: `Verzuimmelding ${monthYearNl(e.startDate)}`,
        description: `Absence report of ${fullName(employee)}`,
        fileSuffix: e.startDate,
        sourceEvent: index,
        values: {
          absenceType: "Sick leave",
          firstDay: e.startDate,
          returnDate: returned,
          reportedTo: company.absenceService,
        },
      });
    });
    return drafts;
  },
};
