import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { examplePreset } from "../src/generate/examplePreset";
import { expandDossiers } from "../src/generate/expand";
import { buildImportXml } from "../src/export/importXml";
import { renderDocument, renderedLines } from "../src/spec/render";
import { canonicalXml } from "./xmlCanon";

/**
 * The golden test: generating from AMEXIO's four example employees must give
 * back AMEXIO's example package. If this passes, the generator understands the
 * format; everything else (more employees, more history, more document types)
 * builds on the same code.
 */

const FIXTURE = join(__dirname, "fixtures", "amexio-example");

describe("AMEXIO example package", () => {
  const set = examplePreset();
  const pkg = expandDossiers(set);

  it("produces the same 5 folders and 20 documents", () => {
    expect(pkg.folders).toHaveLength(5);
    expect(pkg.documents).toHaveLength(20);
    expect(pkg.updates).toHaveLength(1);
  });

  it("reproduces import.xml (elements, attributes and text; comments ignored)", () => {
    const expected = canonicalXml(readFileSync(join(FIXTURE, "import.xml"), "utf8"));
    const actual = canonicalXml(buildImportXml(set, pkg));
    expect(actual).toEqual(expected);
  });

  it("reproduces the text of all 20 PDFs", () => {
    const expected = JSON.parse(readFileSync(join(FIXTURE, "pdf-text.json"), "utf8")) as Record<string, string[]>;
    const byFile = Object.fromEntries(
      pkg.documents.map((d) => {
        const employee = set.employees.find((e) => e.id === d.employeeId)!;
        return [d.fileName, renderedLines(renderDocument(d, employee, set.config.target))];
      }),
    );
    expect(Object.keys(byFile).sort()).toEqual(Object.keys(expected).sort());
    for (const [file, lines] of Object.entries(expected)) {
      expect(byFile[file], file).toEqual(lines);
    }
  });
});
