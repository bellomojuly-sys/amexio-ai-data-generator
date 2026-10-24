import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { examplePreset } from "../src/generate/examplePreset";
import { expandDossiers } from "../src/generate/expand";
import { buildImportXml } from "../src/export/importXml";
import { renderDocument } from "../src/spec/render";
import type { RenderedDocument } from "../src/spec/types";
import type { CanonNode } from "./xmlCanon";
import { canonicalXml } from "./xmlCanon";
import { renderCases, throughCases } from "../src/case/bridge";
import { referenceCase, referenceRun } from "../src/case/reference";
import type { DossierPackage, DossierSet } from "../src/generate/types";
import { extractPdfText } from "./pdfText";

/**
 * The golden test: generating from AMEXIO's four example employees must give
 * back AMEXIO's example package. If this passes, the generator understands the
 * format; everything else (more employees, more history, more document types)
 * builds on the same code.
 *
 * The same comparison runs three ways: from the preset, through the case
 * folders the demo writes (what the export reads), and from the case model's
 * reference case 100101 (BR-14).
 *
 * AMEXIO's mock package is not in git. Put it in
 * generator/generated_mock_data/mock_import_dossier/ (git-ignored), or point
 * AMEXIO_MOCK_DIR at it. Without it this test is skipped.
 */

const MOCK_DIR = process.env.AMEXIO_MOCK_DIR ?? join(__dirname, "..", "..", "generated_mock_data", "mock_import_dossier");
const hasMock = existsSync(join(MOCK_DIR, "import.xml"));

/** The pieces of text a PDF draws, in order: wrapper lines whole, rows as label and value. */
function drawnText(r: RenderedDocument): string[] {
  return [
    r.banner,
    r.title,
    ...r.identity.map((row) => `${row.label}: ${row.value}`),
    ...r.rows.flatMap((row) => [`${row.label}:`, row.value]),
    r.footer,
  ];
}

function expectSamePdfs(set: DossierSet, pkg: DossierPackage) {
  for (const d of pkg.documents) {
    const file = join(MOCK_DIR, "files", d.fileName);
    expect(existsSync(file), `missing in the mock package: ${d.fileName}`).toBe(true);
    const employee = set.employees.find((e) => e.id === d.employeeId)!;
    const expected = extractPdfText(readFileSync(file));
    expect(drawnText(renderDocument(d, employee, set.config.target)), d.fileName).toEqual(expected);
  }
}

const textOf = (node: CanonNode, child: string) => node.children.find((c) => c.name === child)?.text ?? "";

/** The import.xml nodes of one employee: their folder, their documents and updates, and the root folder above them. */
function nodesOf(xml: CanonNode, folderTitle: string): CanonNode {
  return {
    ...xml,
    children: xml.children.filter((n) => {
      const location = textOf(n, "location");
      return location === "Enterprise" || textOf(n, "title") === folderTitle || location.endsWith(`:${folderTitle}`);
    }),
  };
}

describe.runIf(hasMock)("AMEXIO example package", () => {
  const set = examplePreset();
  const pkg = expandDossiers(set);
  const expectedXml = () => canonicalXml(readFileSync(join(MOCK_DIR, "import.xml"), "utf8"));

  it("produces the same 5 folders and 20 documents", () => {
    expect(pkg.folders).toHaveLength(5);
    expect(pkg.documents).toHaveLength(20);
    expect(pkg.updates).toHaveLength(1);
  });

  it("reproduces import.xml (elements, attributes and text; comments ignored)", () => {
    expect(canonicalXml(buildImportXml(set, pkg))).toEqual(expectedXml());
  });

  it("reproduces the text of all 20 PDFs", () => {
    expectSamePdfs(set, pkg);
  });

  it("reproduces import.xml and the 20 PDFs from the saved case folders", () => {
    const stage = throughCases(set);
    expect(stage.pkg.documents).toHaveLength(20);
    expect(canonicalXml(buildImportXml(stage.read.set, stage.pkg))).toEqual(expectedXml());
    expectSamePdfs(stage.read.set, stage.pkg);
  });

  it("BR-14: the reference case 100101 renders as AMEXIO's 5 PDFs and import.xml entries", () => {
    const stage = renderCases([referenceCase()], referenceRun());
    expect(stage.read.problems).toEqual([]);
    expect(stage.pkg.documents).toHaveLength(5);
    const expected = nodesOf(expectedXml(), "100101 Jan de Vries");
    expect(expected.children).toHaveLength(8); // root folder, employee folder, 5 documents, 1 update
    expect(canonicalXml(buildImportXml(stage.read.set, stage.pkg))).toEqual(expected);
    expectSamePdfs(stage.read.set, stage.pkg);
  });

  it("BR-14: a fact removed from the reference case (the examiner) no longer matches", () => {
    const c = referenceCase();
    delete c.personas!["P003"];
    c.events!["EVT-003"].participant_ids = ["P001"];
    const stage = renderCases([c], referenceRun());
    expect(() => expectSamePdfs(stage.read.set, stage.pkg)).toThrow();
  });
});

describe.skipIf(hasMock)("AMEXIO example package", () => {
  it.skip(`skipped: AMEXIO's mock package was not found in ${MOCK_DIR}`, () => {});
});
