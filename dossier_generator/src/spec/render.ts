import { isISODate } from "../model/dates";
import type { Employee } from "../model/dossier";
import { fullName } from "../model/dossier";
import { docType } from "./doctypes";
import { days, eurGrouped, eurPlain, monthYear, pdfDate } from "./format";
import type { TargetProfile } from "./target";
import type { DocumentInstance, FieldFormat, FieldValue, RenderedDocument, RenderedRow } from "./types";

/** Formats one stored value the way the PDF prints it. */
export function formatValue(value: FieldValue, format: FieldFormat): string {
  if (typeof value === "object") {
    return `${pdfDate(value.from)} to ${pdfDate(value.to)}`;
  }
  switch (format) {
    case "date":
      return typeof value === "string" && isISODate(value) ? pdfDate(value) : String(value);
    case "monthYear":
      return typeof value === "string" && isISODate(value) ? monthYear(value) : String(value);
    case "eurGrouped":
      return eurGrouped(Number(value));
    case "eurPlain":
      return eurPlain(Number(value));
    case "days":
      return days(Number(value));
    case "dateRange":
    case "number":
    case "text":
    default:
      return String(value);
  }
}

/**
 * Everything one PDF shows, in print order: AMEXIO's shared wrapper (banner,
 * title, employee block, footer) around the document type's own rows.
 */
export function renderDocument(doc: DocumentInstance, employee: Employee, target: TargetProfile): RenderedDocument {
  const spec = docType(doc.docType);
  const rows: RenderedRow[] = [];
  for (const field of spec.fields) {
    const value = doc.values[field.key];
    if (value === undefined || value === "") {
      if (field.optional) continue;
      rows.push({ label: field.label, value: "", origin: field.origin, fieldKey: field.key });
      continue;
    }
    rows.push({ label: field.label, value: formatValue(value, field.format), origin: field.origin, fieldKey: field.key });
  }
  const name = fullName(employee);
  return {
    banner: target.bannerText,
    title: doc.title,
    identity: [
      { label: "Employee", value: name, origin: "persona", fieldKey: "employee" },
      { label: "Employee ID", value: employee.id, origin: "rule", fieldKey: "employeeId" },
      { label: "Department", value: employee.department, origin: "persona", fieldKey: "department" },
    ],
    rows,
    footer: target.footerText,
    pdfTitle: `${doc.title} - ${name}`,
  };
}

/** The PDF's text, line by line, as `pdftotext -raw` reads it. Used by tests and the validator. */
export function renderedLines(r: RenderedDocument): string[] {
  return [
    r.banner,
    r.title,
    ...r.identity.map((row) => `${row.label}: ${row.value}`),
    ...r.rows.map((row) => `${row.label}: ${row.value}`),
    r.footer,
  ];
}
