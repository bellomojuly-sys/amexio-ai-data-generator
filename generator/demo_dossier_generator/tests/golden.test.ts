import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { examplePreset } from "../src/generate/examplePreset";
import { expandDossiers } from "../src/generate/expand";
import { buildImportXml } from "../src/export/importXml";
import { renderDocument } from "../src/spec/render";
import type { RenderedDocument } from "../src/spec/types";
import { canonicalXml } from "./xmlCanon";
import { extractPdfText } from "./pdfText";

/**
 * The golden test: generating from AMEXIO's four example employees must give
 * back AMEXIO's example package. If this passes, the generator understands the
 * format; everything else (more employees, more history, more document types)
 * builds on the same code.
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

describe.runIf(hasMock)("AMEXIO example package", () => {
  const set = examplePreset();
  const pkg = expandDossiers(set);

  it("produces the same 5 folders and 20 documents", () => {
    expect(pkg.folders).toHaveLength(5);
    expect(pkg.documents).toHaveLength(20);
    expect(pkg.updates).toHaveLength(1);
  });

  it("reproduces import.xml (elements, attributes and text; comments ignored)", () => {
    const expected = canonicalXml(readFileSync(join(MOCK_DIR, "import.xml"), "utf8"));
    const actual = canonicalXml(buildImportXml(set, pkg));
    expect(actual).toEqual(expected);
  });

  it("reproduces the text of all 20 PDFs", () => {
    for (const d of pkg.documents) {
      const file = join(MOCK_DIR, "files", d.fileName);
      expect(existsSync(file), `missing in the mock package: ${d.fileName}`).toBe(true);
      const employee = set.employees.find((e) => e.id === d.employeeId)!;
      const expected = extractPdfText(readFileSync(file));
      expect(drawnText(renderDocument(d, employee, set.config.target)), d.fileName).toEqual(expected);
    }
  });
});

describe.skipIf(hasMock)("AMEXIO example package", () => {
  it.skip(`skipped: AMEXIO's mock package was not found in ${MOCK_DIR}`, () => {});
});
