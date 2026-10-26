import { fullName } from "../../model/dossier";
import { MEDICAL_ACL } from "../target";
import { nextMedicalCheck } from "../rules";
import type { DocDraft, DocTypeSpec } from "../types";

/**
 * [2] Medical check — in AMEXIO's example.
 *
 * Privacy: Dutch rules generally do not let an employer record diagnoses, so the
 * document holds only the occupational physician's conclusion about fitness for
 * work. Only the HR Medical group may open it.
 */
export const medicalCheck: DocTypeSpec = {
  id: "medical_check",
  documentType: "Medical Check",
  slug: "medical_check",
  origin: "amexio",
  summary: "Outcome of the periodic occupational health check. No diagnoses, only the fitness conclusion.",
  occurs: "Every 2 years. Each check is held on the 'Next check' date of the previous one.",
  titlePattern: "Medical Check (+ year when there is more than one)",
  tags: ["medical", "health"],
  confidential: true,
  acl: MEDICAL_ACL,
  fields: [
    { key: "examDate", label: "Examination date", format: "date", origin: "storyline" },
    { key: "examiner", label: "Examined by", format: "text", origin: "constant" },
    { key: "result", label: "Result", format: "text", origin: "storyline", rule: "Fitness conclusion only." },
    { key: "nextCheck", label: "Next check", format: "date", origin: "rule", rule: "Examination date + 2 years." },
  ],
  dateField: "examDate",
  rules: [
    "Next check = examination date + 2 years.",
    "A follow-up check is held on the previous check's 'Next check' date.",
    "Access: HR Medical group only; everyone else (world) gets no rights.",
  ],
  plan({ employee, timeline, company, asOf, windowStart }) {
    const drafts: DocDraft[] = [];
    timeline.events.forEach((e, index) => {
      if (e.type !== "medical_check") return;
      if (e.date > asOf || e.date < windowStart) return;
      drafts.push({
        date: e.date,
        title: "Medical Check",
        titleNl: "Medische keuring",
        titleIfMany: `Medical Check ${e.date.slice(0, 4)}`,
        titleNlIfMany: `Medische keuring ${e.date.slice(0, 4)}`,
        description: `Occupational health check result of ${fullName(employee)}`,
        fileSuffix: e.date,
        sourceEvent: index,
        values: { examDate: e.date, examiner: company.examiner, result: e.result, nextCheck: nextMedicalCheck(e.date) },
      });
    });
    return drafts;
  },
};
