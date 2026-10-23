import { fullName } from "../../model/dossier";
import type { DocDraft, DocTypeSpec } from "../types";

/** [5] Training certificate — in AMEXIO's example. One per completed course. */
export const trainingCertificate: DocTypeSpec = {
  id: "training_certificate",
  documentType: "Training Certificate",
  slug: "training_certificate",
  origin: "amexio",
  summary: "Proof that the employee completed a course.",
  occurs: "Once per completed course. The AI picks courses that fit the employee's job.",
  titlePattern: "Training Certificate (+ course name when there is more than one)",
  tags: ["training", "certificate"],
  confidential: false,
  acl: [],
  fields: [
    { key: "course", label: "Course", format: "text", origin: "storyline" },
    { key: "completedOn", label: "Completed on", format: "date", origin: "storyline" },
    { key: "provider", label: "Provider", format: "text", origin: "constant" },
    { key: "duration", label: "Duration", format: "days", origin: "storyline" },
  ],
  dateField: "completedOn",
  rules: [
    "Completed on = document date; between the start date and the last working day.",
    "Titles must be unique in the folder, so a second certificate carries the course name.",
  ],
  plan({ employee, timeline, company, asOf, windowStart }) {
    const drafts: DocDraft[] = [];
    timeline.events.forEach((e, index) => {
      if (e.type !== "training") return;
      if (e.date > asOf || e.date < windowStart) return;
      drafts.push({
        date: e.date,
        title: "Training Certificate",
        titleNl: "Trainingscertificaat",
        titleIfMany: `Training Certificate ${e.course}`,
        titleNlIfMany: `Trainingscertificaat ${e.course}`,
        description: `Completed training certificate of ${fullName(employee)}`,
        fileSuffix: e.date,
        sourceEvent: index,
        values: { course: e.course, completedOn: e.date, provider: company.trainingProvider, duration: e.durationDays },
      });
    });
    return drafts;
  },
};
