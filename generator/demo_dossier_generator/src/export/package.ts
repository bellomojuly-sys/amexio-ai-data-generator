import { zipSync, strToU8 } from "fflate";
import { fullName } from "../model/dossier";
import { DOC_TYPES } from "../spec/doctypes";
import { renderDocument } from "../spec/render";
import type { DossierPackage, DossierSet } from "../generate/types";
import { buildImportXml } from "./importXml";
import { renderPdf } from "./pdf";
import { formatSpec } from "../spec/exportSpec";

/**
 * Builds the import package in the same layout as AMEXIO's example:
 *
 *   {packageName}/
 *   ├── README.md        what is in the package and how it was made
 *   ├── import.xml       the Object Importer control file
 *   ├── generation.json  the facts the documents were made from (config, personas, storylines)
 *   ├── cases/           the same facts in the case model's format: one folder per employee
 *   │                    (case.json, cast.json, storyline.json, documents.json), plus
 *   │                    employees.json and storylines.json for python -m case_model.ingest
 *   └── files/           one PDF per document
 */

export interface PackageExtras {
  /** Extra text files by path inside the package, e.g. "cases/100101/case.json". */
  files?: Record<string, string>;
  /** What generation.json records (the generation run); defaults to the set the documents were made from. */
  record?: DossierSet;
}

export interface PackageProgress {
  done: number;
  total: number;
  phase: "pdf" | "zip";
}

export async function buildPackageFiles(
  set: DossierSet,
  pkg: DossierPackage,
  onProgress?: (p: PackageProgress) => void,
  signal?: AbortSignal,
  extras: PackageExtras = {},
): Promise<Record<string, Uint8Array>> {
  const root = set.config.target.packageName;
  const files: Record<string, Uint8Array> = {};
  const byId = new Map(set.employees.map((e) => [e.id, e]));
  const total = pkg.documents.length;
  for (let i = 0; i < total; i++) {
    if (signal?.aborted) throw new DOMException("Export cancelled", "AbortError");
    const doc = pkg.documents[i];
    const employee = byId.get(doc.employeeId)!;
    files[`${root}/files/${doc.fileName}`] = await renderPdf(renderDocument(doc, employee, set.config.target), doc.date);
    if (i % 25 === 0 || i === total - 1) {
      onProgress?.({ done: i + 1, total, phase: "pdf" });
      await new Promise((r) => setTimeout(r, 0));
    }
  }
  files[`${root}/import.xml`] = strToU8(buildImportXml(set, pkg));
  const extra = extras.files ?? {};
  files[`${root}/README.md`] = strToU8(buildReadme(set, pkg, Object.keys(extra).some((p) => p.startsWith("cases/"))));
  files[`${root}/generation.json`] = strToU8(JSON.stringify(generationRecord(extras.record ?? set), null, 2));
  for (const [path, text] of Object.entries(extra)) files[`${root}/${path}`] = strToU8(text);
  return files;
}

export async function buildZip(
  set: DossierSet,
  pkg: DossierPackage,
  onProgress?: (p: PackageProgress) => void,
  signal?: AbortSignal,
  extras: PackageExtras = {},
): Promise<Uint8Array> {
  const files = await buildPackageFiles(set, pkg, onProgress, signal, extras);
  onProgress?.({ done: pkg.documents.length, total: pkg.documents.length, phase: "zip" });
  await new Promise((r) => setTimeout(r, 0));
  // PDFs are already compressed; store them, deflate the text files.
  const entries: Record<string, [Uint8Array, { level: 0 | 6 }]> = {};
  for (const [path, data] of Object.entries(files)) {
    entries[path] = [data, { level: path.endsWith(".pdf") ? 0 : 6 }];
  }
  return zipSync(entries);
}

export function generationRecord(set: DossierSet) {
  return {
    note: "Synthetic data. These are the facts every document in this package was made from.",
    generationId: set.generationId,
    provenance: set.provenance,
    config: set.config,
    employees: set.employees,
    storylines: set.storylines,
    corrections: set.corrections,
    overrides: set.overrides,
    formatSpecVersion: formatSpec().version,
  };
}

export function countsByType(pkg: DossierPackage): { id: string; label: string; count: number; origin: string }[] {
  return DOC_TYPES.map((d) => ({
    id: d.id,
    label: d.documentType,
    origin: d.origin,
    count: pkg.documents.filter((x) => x.docType === d.id).length,
  })).filter((r) => r.count > 0);
}

export function buildReadme(set: DossierSet, pkg: DossierPackage, withCases = false): string {
  const c = set.config;
  const counts = countsByType(pkg);
  const leavers = set.employees.filter((e) => set.storylines[e.id]?.events.some((ev) => ev.type === "termination"));
  const lines = [
    `# ${c.target.packageName}`,
    ``,
    `Synthetic HR dossiers for OpenText Content Server, made with the AMEXIO dossier generator demo.`,
    `**All people, numbers and organisations are fictional.** Every PDF carries the banner "${c.target.bannerText}".`,
    ``,
    `| | |`,
    `| --- | --- |`,
    `| Generation | ${set.generationId} |`,
    `| Seed | ${c.seed} |`,
    `| As of | ${c.asOf} |`,
    `| Personas from | ${set.provenance.personas ?? "-"} |`,
    `| Storylines from | ${set.provenance.storylines ?? "-"} |`,
    `| Employees | ${set.employees.length} (${leavers.length} left the company) |`,
    `| Folders | ${pkg.folders.length} |`,
    `| Documents | ${pkg.documents.length} |`,
    ``,
    `## Documents by type`,
    ``,
    `| Document Type | Count | In AMEXIO's example? |`,
    `| --- | ---: | --- |`,
    ...counts.map((r) => `| ${r.label} | ${r.count} | ${r.origin === "amexio" ? "yes" : "no, proposed extension"} |`),
    ``,
    `## Employees`,
    ``,
    `| Folder | Position | Department | Hired |`,
    `| --- | --- | --- | --- |`,
    ...set.employees.map((e) => `| ${e.id} ${fullName(e)} | ${e.position} | ${e.department} | ${e.hireDate} |`),
    ``,
    `## How to import`,
    ``,
    `1. Unpack this package to \`${c.target.basePath}\` on the Object Importer server, so the paths in \`import.xml\` (\`${c.target.basePath}${c.target.packageName}\\files\\...\`) point at the PDFs.`,
    `2. Make sure these already exist in Content Server: category \`${c.target.categoryName}\`, user(s) ${c.target.knownUsers.map((u) => `\`${u}\``).join(", ")}, group(s) ${c.target.knownGroups.map((g) => `\`${g}\``).join(", ")}. The import never creates them.`,
    `3. Run Object Importer on \`import.xml\`.`,
    ``,
    `## Files`,
    ``,
    `- \`import.xml\`: the control file. Folders first, then documents, then updates.`,
    `- \`files/\`: one PDF per document. Names are \`{employee id}_{type}.pdf\`, with a date or year added when an employee has more than one document of a type.`,
    `- \`generation.json\`: the configuration, personas and storylines every document was made from, so the package can be checked or made again.`,
    ...(withCases
      ? [
          `- \`cases/\`: the same facts in the case model's format (v1.1), one folder per employee: \`case.json\`, \`cast.json\` (personas, organisations, employment), \`storyline.json\` (events, EVT-001 is the hire) and \`documents.json\` (one entry per PDF, DOC-001... in date order, each pointing at the event it records). The PDFs and \`import.xml\` were made from these folders. \`cases/employees.json\` and \`cases/storylines.json\` are the same run as input for \`python -m case_model.ingest\`.`,
        ]
      : []),
    ``,
    `## Assumptions`,
    ``,
    `- Format, category, attribute names, users and groups follow AMEXIO's mock import package.`,
    `- Document types marked "proposed extension" are not in AMEXIO's example and need confirmation.`,
    `- Wage tax is a flat 37% (rounded half to even), as in the example.`,
    ``,
    `## Document type rules`,
    ``,
    ...DOC_TYPES.filter((d) => c.docTypes.includes(d.id)).flatMap((d) => [
      `### ${d.documentType}${d.origin === "extension" ? " (proposed extension)" : ""}`,
      ``,
      `${d.summary} ${d.occurs}`,
      ``,
      ...d.rules.map((r) => `- ${r}`),
      ``,
    ]),
  ];
  return lines.join("\n");
}
