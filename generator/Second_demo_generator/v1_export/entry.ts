/**
 * Demo stand-in for Export (step 9, Stylianos): v1's own export, unchanged.
 *
 * The chain ends at complete cases (contract §3); Export, which turns them into
 * AMEXIO's PDFs and import.xml, does not exist in Python yet. v1
 * (generator/demo_dossier_generator, frozen) already does this from case
 * folders: its Configure step, "Open case ZIP", reads them, renders every
 * document, checks the result and builds the package. This module runs exactly
 * those functions of v1's source on the case folders the v2 page exports, so
 * the v2 ZIP holds the same package v1 would make from it. Nothing of v1 is
 * copied or changed: build_v1_export.mjs bundles v1's files as they are.
 */
import { strToU8, zipSync } from "fflate";
import { readCaseFiles, renderCases } from "../../demo_dossier_generator/src/case/bridge";
import { buildImportXml } from "../../demo_dossier_generator/src/export/importXml";
import { buildPackageFiles, countsByType } from "../../demo_dossier_generator/src/export/package";
import { cloneConfig, DEFAULT_CONFIG } from "../../demo_dossier_generator/src/generate/config";
import { validate } from "../../demo_dossier_generator/src/validate/validate";

export interface PackageCheck {
  /** v1's package folder, as in its own ZIP. */
  packageName: string;
  /** True when the package is in the ZIP: v1's checks found no error. */
  made: boolean;
  cases: number;
  documents: number;
  pdfs: number;
  errors: number;
  warnings: number;
  /** v1's errors and warnings, as its Validate step lists them. */
  issues: { severity: string; code: string; message: string; employeeId?: string }[];
  /** Case folders v1 could not read (they are left out of the package). */
  problems: { employeeId: string; message: string }[];
  counts: { id: string; label: string; count: number }[];
}

/** As v1's useGenerator: import.xml must parse as XML. */
function parseXml(text: string): string | null {
  if (typeof DOMParser === "undefined") return null;
  const doc = new DOMParser().parseFromString(text, "application/xml");
  const err = doc.getElementsByTagName("parsererror")[0];
  return err ? (err.textContent ?? "parse error").slice(0, 200) : null;
}

/**
 * The package for the case folders ("100101/case.json", ...), as v1's "Open
 * case ZIP" makes it: v1's default settings, with the run's as-of date (v1
 * plans the documents up to it). Like v1's Export step, no package when its
 * checks find an error; the check says why.
 */
export async function makePackage(
  caseFiles: Record<string, string>,
  asOf: string,
  onProgress?: (done: number, total: number) => void,
): Promise<{ check: PackageCheck; files: Record<string, Uint8Array> }> {
  const cases = readCaseFiles(caseFiles);
  if (!cases.length) throw new Error("The run has no case folders.");
  const config = cloneConfig(DEFAULT_CONFIG);
  config.asOf = asOf;
  const stage = renderCases(cases, { config });
  const { set } = stage.read;
  const { pkg } = stage;
  const report = validate(set, pkg, { cases: stage.cases, xml: buildImportXml(set, pkg), parseXml });
  const check: PackageCheck = {
    packageName: set.config.target.packageName,
    made: report.errors === 0,
    cases: cases.length,
    documents: pkg.documents.length,
    pdfs: 0,
    errors: report.errors,
    warnings: report.warnings,
    issues: report.issues
      .filter((i) => i.severity !== "info")
      .map((i) => ({ severity: i.severity, code: i.code, message: i.message, ...(i.employeeId ? { employeeId: i.employeeId } : {}) })),
    problems: stage.read.problems,
    counts: countsByType(pkg).map(({ id, label, count }) => ({ id, label, count })),
  };
  if (!check.made) return { check, files: {} };
  const files = await buildPackageFiles(set, pkg, (p) => onProgress?.(p.done, p.total));
  check.pdfs = Object.keys(files).filter((p) => p.endsWith(".pdf")).length;
  return { check, files };
}

/** A ZIP of text and binary files; PDFs are stored (already compressed), the rest deflated, as v1 does. */
export function zip(files: Record<string, string | Uint8Array>): Uint8Array {
  const entries: Record<string, [Uint8Array, { level: 0 | 6 }]> = {};
  for (const [path, data] of Object.entries(files)) {
    entries[path] = [typeof data === "string" ? strToU8(data) : data, { level: path.endsWith(".pdf") ? 0 : 6 }];
  }
  return zipSync(entries);
}
