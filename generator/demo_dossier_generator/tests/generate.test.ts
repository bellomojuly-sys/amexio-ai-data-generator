import { describe, expect, it } from "vitest";
import { DOMParser } from "@xmldom/xmldom";
import { cloneConfig, DEFAULT_CONFIG } from "../src/generate/config";
import { expandDossiers } from "../src/generate/expand";
import { examplePreset } from "../src/generate/examplePreset";
import { generateOffline } from "../src/generate/offline";
import { buildImportXml } from "../src/export/importXml";
import { validate } from "../src/validate/validate";
import { BREAKERS } from "../src/validate/breakers";
import { wageTax } from "../src/spec/rules";
import { eurGrouped, eurPlain, pdfDate, xmlDate } from "../src/spec/format";

const parseXml = (xml: string) => {
  let error: string | null = null;
  new DOMParser({ errorHandler: { error: (m: string) => (error = m), fatalError: (m: string) => (error = m), warning: () => {} } }).parseFromString(xml, "text/xml");
  return error;
};

describe("rules and formats", () => {
  it("rounds wage tax half to even, like the example", () => {
    expect(wageTax(4350)).toBe(1610);
    expect(wageTax(3900)).toBe(1443);
    expect(wageTax(3450)).toBe(1276);
    expect(wageTax(5100)).toBe(1887);
  });
  it("formats dates and money per output", () => {
    expect(pdfDate("2026-04-14")).toBe("14-04-2026");
    expect(xmlDate("2026-04-14")).toBe("20260414");
    expect(eurGrouped(4350)).toBe("EUR 4.350");
    expect(eurGrouped(1234567)).toBe("EUR 1.234.567");
    expect(eurPlain(4350)).toBe("EUR 4350");
  });
});

describe("offline generation", () => {
  const seeds = [1, 2, 3, 7, 42, 2026, 31337];
  for (const seed of seeds) {
    it(`seed ${seed}: full history passes every check`, () => {
      const config = cloneConfig(DEFAULT_CONFIG);
      config.seed = seed;
      config.employeeCount = 14;
      config.historyYears = 5;
      const set = generateOffline(config);
      const pkg = expandDossiers(set);
      const xml = buildImportXml(set, pkg);
      const report = validate(set, pkg, { xml, parseXml });
      const errors = report.issues.filter((i) => i.severity === "error");
      expect(errors, errors.map((e) => e.message).join("\n")).toEqual([]);
      expect(pkg.documents.length).toBeGreaterThan(14 * 10);
    });
  }

  it("is reproducible: same seed, same documents", () => {
    const a = expandDossiers(generateOffline({ ...cloneConfig(DEFAULT_CONFIG), seed: 99 }));
    const b = expandDossiers(generateOffline({ ...cloneConfig(DEFAULT_CONFIG), seed: 99 }));
    expect(a.documents.map((d) => [d.fileName, d.values])).toEqual(b.documents.map((d) => [d.fileName, d.values]));
  });

  it("covers leavers, amendments, absences and statements", () => {
    const config = cloneConfig(DEFAULT_CONFIG);
    config.employeeCount = 20;
    config.historyYears = 6;
    const pkg = expandDossiers(generateOffline(config));
    const types = new Set(pkg.documents.map((d) => d.docType));
    for (const t of ["termination_letter", "contract_amendment", "absence_report", "annual_income_statement"]) {
      expect(types.has(t as never), t).toBe(true);
    }
  });

  it("'latest' history gives one document per type, like the example", () => {
    const config = cloneConfig(DEFAULT_CONFIG);
    config.history = "latest";
    const pkg = expandDossiers(generateOffline(config));
    const keys = pkg.documents.map((d) => `${d.employeeId}/${d.docType}`);
    expect(new Set(keys).size).toBe(keys.length);
    expect(pkg.documents.every((d) => !/_\d{4}/.test(d.fileName))).toBe(true);
  });

  it("the AMEXIO example passes every check", () => {
    const set = examplePreset();
    const pkg = expandDossiers(set);
    const report = validate(set, pkg, { xml: buildImportXml(set, pkg), parseXml });
    expect(report.errors).toBe(0);
    expect(report.warnings).toBe(0);
  });
});

describe("validator catches planted mistakes", () => {
  for (const breaker of BREAKERS) {
    it(breaker.label, () => {
      const config = cloneConfig(DEFAULT_CONFIG);
      config.seed = 5;
      const set = generateOffline(config);
      const pkg = expandDossiers(set);
      const what = breaker.apply(set, pkg);
      expect(what).not.toBeNull();
      const report = validate(set, pkg);
      expect(report.errors).toBeGreaterThan(0);
    });
  }
});
