import { DOC_TYPES } from "./doctypes";
import { DEFAULT_TARGET } from "./target";
import { PAY_DAY, WAGE_TAX_PERCENT, MEDICAL_INTERVAL_YEARS } from "./rules";

/**
 * The format spec as plain JSON: the machine-readable replacement for the
 * "AMEXIO Full Dossier Format" Word document. Generated from the TypeScript
 * modules, so it can never drift from what the generator actually does.
 */
export function formatSpec() {
  return {
    version: "0.1.0",
    source: "AMEXIO mock-import-dossier (October 2026) + proposed extensions",
    wrapper: {
      banner: DEFAULT_TARGET.bannerText,
      identityBlock: ["Employee: {full name}", "Employee ID: {employee id}", "Department: {department}"],
      footer: DEFAULT_TARGET.footerText,
      layout:
        "A4. Red banner (RGB 192,57,43) 22 mm high with the banner text in white Helvetica-Bold 16 pt, centred. Title Helvetica-Bold 22 pt. Employee block Helvetica 12 pt. Horizontal rule. Rows: label Helvetica-Bold 12 pt at 2 cm, value Helvetica 12 pt at 8 cm, 8 mm apart. Footer Helvetica-Oblique 9 pt grey at 2 cm from the bottom.",
      pdfMetadataTitle: "{document title} - {full name}",
    },
    formats: {
      pdfDate: "DD-MM-YYYY",
      xmlDate: "YYYYMMDD",
      contractMoney: "EUR 4.350 ('.' thousands separator)",
      payrollMoney: "EUR 4350 (no separator)",
      fileName: "{employee id}_{slug}.pdf, or {employee id}_{slug}_{date or year}.pdf when an employee has more than one of a type",
      folder: "{root location}:{root folder}:{employee id} {full name}",
    },
    rules: {
      payDay: PAY_DAY,
      wageTaxPercent: WAGE_TAX_PERCENT,
      wageTaxRounding: "half to even",
      medicalIntervalYears: MEDICAL_INTERVAL_YEARS,
    },
    target: DEFAULT_TARGET,
    documentTypes: DOC_TYPES.map((d) => ({
      id: d.id,
      documentType: d.documentType,
      origin: d.origin,
      slug: d.slug,
      summary: d.summary,
      occurs: d.occurs,
      titlePattern: d.titlePattern,
      tags: d.tags,
      confidential: d.confidential,
      acl: d.acl,
      fields: d.fields,
      rules: d.rules,
    })),
  };
}
