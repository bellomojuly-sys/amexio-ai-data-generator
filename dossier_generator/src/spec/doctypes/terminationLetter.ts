import { addMonths, monthEnd } from "../../model/dates";
import { fullName } from "../../model/dossier";
import type { DocDraft, DocTypeSpec } from "../types";

/**
 * Termination letter — EXTENSION, not in AMEXIO's example.
 * Shows a different outcome: an employee who leaves. Nothing in the dossier may
 * be dated after the last working day, except the annual income statement.
 */
export const terminationLetter: DocTypeSpec = {
  id: "termination_letter",
  documentType: "Termination Letter",
  slug: "termination_letter",
  origin: "extension",
  summary: "Confirms the end of employment, its reason and the last working day.",
  occurs: "Once, for employees who leave. Dated on the notice date.",
  titlePattern: "Termination Letter",
  tags: ["termination", "legal"],
  confidential: true,
  acl: [],
  fields: [
    { key: "noticeDate", label: "Date of notice", format: "date", origin: "rule", rule: "One month before the last working day, unless the storyline gives a date." },
    { key: "lastDay", label: "Last working day", format: "date", origin: "storyline", rule: "Always the last day of a month." },
    { key: "reason", label: "Reason", format: "text", origin: "storyline" },
    { key: "finalPayslip", label: "Final payslip", format: "monthYear", origin: "rule", rule: "The month of the last working day." },
  ],
  dateField: "noticeDate",
  rules: [
    "Last working day is the last day of a month; no payslip, appraisal or check after it.",
    "Notice date = document date, before the last working day.",
  ],
  plan({ employee, timeline, asOf }) {
    const drafts: DocDraft[] = [];
    timeline.events.forEach((e, index) => {
      if (e.type !== "termination") return;
      const noticeDate = e.noticeDate ?? addMonths(monthEnd(e.date), -1);
      if (noticeDate > asOf) return;
      drafts.push({
        date: noticeDate,
        title: "Termination Letter",
        titleNl: "Beëindiging dienstverband",
        description: `Termination letter of ${fullName(employee)}`,
        fileSuffix: noticeDate,
        sourceEvent: index,
        values: { noticeDate, lastDay: e.date, reason: e.reason, finalPayslip: e.date },
      });
    });
    return drafts;
  },
};
