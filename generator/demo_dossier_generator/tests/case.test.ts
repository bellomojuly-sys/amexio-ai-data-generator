import { readFileSync } from "node:fs";
import { join } from "node:path";
import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { describe, expect, it } from "vitest";
import { caseExportFiles, ingestInput, readCaseFiles, renderCases, throughCases } from "../src/case/bridge";
import { caseFolder, caseFolderFiles, pyJson, readCaseFolder } from "../src/case/caseJson";
import { checkCase } from "../src/case/checkCase";
import type { Case } from "../src/case/generated/case";
import { referenceCase, referenceRun } from "../src/case/reference";
import { toCases } from "../src/case/toCase";
import { cloneConfig, DEFAULT_CONFIG } from "../src/generate/config";
import { examplePreset } from "../src/generate/examplePreset";
import { expandDossiers } from "../src/generate/expand";
import { generateOffline } from "../src/generate/offline";
import type { DossierSet } from "../src/generate/types";
import type { DocumentInstance } from "../src/spec/types";
import { validate } from "../src/validate/validate";
import { CASE_MODEL_DIR, OUT_DIR, renderCaseTypes, SCHEMA_DIR } from "../scripts/caseTypes";
import { committedFixtures, FIXTURE_DIR, renderFixtures } from "../scripts/caseFixtures";

/**
 * The bridge to the case model (case_model/, branch case-model-v1.1).
 * The Python side runs the same fixtures through load_case and ingest
 * (case_model/test_demo_cases.py); these tests keep the TypeScript side honest
 * without Python.
 */

/** Line endings are git's business (see .gitattributes); the content is ours. */
const lf = (text: string) => text.replace(/\r\n/g, "\n");
const GOLDEN = lf(readFileSync(join(CASE_MODEL_DIR, "reference_dossier.golden.json"), "utf8"));

function offline(seed: number, patch: (c: typeof DEFAULT_CONFIG) => void = () => {}): DossierSet {
  const c = cloneConfig(DEFAULT_CONFIG);
  c.seed = seed;
  c.employeeCount = 12;
  c.historyYears = 4;
  patch(c);
  return generateOffline(c);
}

const RUNS: [string, () => DossierSet][] = [
  ["AMEXIO example", examplePreset],
  ["offline, seed 1", () => offline(1)],
  ["offline, seed 2026, many leavers", () => offline(2026, (c) => (c.scenario = { ...c.scenario, leaverShare: 0.5, absenceShare: 0.8 }))],
  ["offline, latest documents only", () => offline(5, (c) => (c.history = "latest"))],
];

/** A document without the case's IDs, to compare a run with its round trip through the cases. */
function plain(d: DocumentInstance) {
  const { caseDocId: _a, caseEventId: _b, participantIds: _c, ...rest } = d;
  return rest;
}

function schemaValidator(file: string) {
  const ajv = new Ajv2020({ strict: false, allErrors: true });
  addFormats(ajv);
  return ajv.compile(JSON.parse(readFileSync(join(SCHEMA_DIR, file), "utf8")));
}

describe("files mirrored from case_model/", () => {
  it("the generated types and the bundled reference case are up to date (npm run types)", async () => {
    for (const [name, text] of Object.entries(await renderCaseTypes())) {
      expect(lf(readFileSync(join(OUT_DIR, name), "utf8")), name).toBe(lf(text));
    }
  });

  it("the committed demo fixtures are up to date (npm run fixtures)", () => {
    expect(committedFixtures()).toEqual(renderFixtures());
  }, 30_000);
});

describe("case files", () => {
  it("are written byte for byte like save_case (sorted keys, 2 spaces, 40.0 for hours)", () => {
    expect(pyJson(JSON.parse(GOLDEN))).toBe(GOLDEN);
    expect(pyJson({ b: 1, a: { hours: 40, new_hours: 37.5, year: 2026, note: "Ä & \"q\"" } })).toBe(
      '{\n  "a": {\n    "hours": 40.0,\n    "new_hours": 37.5,\n    "note": "Ä & \\"q\\"",\n    "year": 2026\n  },\n  "b": 1\n}\n',
    );
  });

  it("read back into the same case", () => {
    for (const c of toCases(offline(3))) expect(readCaseFolder(caseFolder(c))).toEqual(c);
  });

  it("fill in the optional fields a hand-written case leaves out, as pydantic does", () => {
    const c = referenceCase();
    const files = caseFolder(c);
    const cast = JSON.parse(files["cast.json"]);
    for (const p of Object.values(cast.personas) as Record<string, unknown>[]) {
      delete p.address;
      delete p.salutation;
      delete p.date_of_birth;
    }
    const story = JSON.parse(files["storyline.json"]);
    delete story.events["EVT-004"].comment;
    delete story.events["EVT-001"].label;
    const read = readCaseFolder({ ...files, "cast.json": JSON.stringify(cast), "storyline.json": JSON.stringify(story) });
    expect(read).toEqual(c);
  });

  it("refuse a folder that is missing a file", () => {
    const { "documents.json": _, ...rest } = caseFolder(referenceCase());
    expect(() => readCaseFolder(rest, "100101")).toThrow(/missing documents\.json/);
  });
});

describe("toCases", () => {
  it("makes AMEXIO's 100101 exactly as the case model's reference case, documents aside (BR-15)", () => {
    const [c] = toCases(examplePreset());
    expect(pyJson({ ...c, documents: {} })).toBe(GOLDEN);
  });

  it("gives every document an ID in date order and the event it records", () => {
    const [c] = toCases(examplePreset());
    const docs = Object.values(c.documents ?? {});
    expect(docs.map((d) => [d.id, d.type, d.event_id])).toEqual([
      ["DOC-001", "employment_contract", "EVT-001"],
      ["DOC-002", "training_certificate", "EVT-002"],
      ["DOC-003", "medical_check", "EVT-003"],
      ["DOC-004", "performance_appraisal", "EVT-004"],
      ["DOC-005", "payslip", null],
    ]);
    expect(docs.map((d) => d.metadata.document_date)).toEqual([...docs.map((d) => d.metadata.document_date)].sort());
    expect(c.documents?.["DOC-003"].participant_ids).toEqual(["P001", "P003"]);
    expect(c.documents?.["DOC-004"].participant_ids).toEqual(["P001", "P002"]);
  });

  it.each(RUNS)("%s: every case follows the case model's rules and its JSON Schema", (_, run) => {
    const valid = schemaValidator("case.schema.json");
    for (const c of toCases(run())) {
      expect(checkCase(c), c.case_number).toEqual([]);
      expect(valid(JSON.parse(pyJson(c))), `${c.case_number}: ${JSON.stringify(valid.errors?.slice(0, 3))}`).toBe(true);
    }
  });

  it("writes Money with cents, snake_case names, a hire event and appraisals on 30 June", () => {
    const set = offline(4, (c) => (c.scenario = { ...c.scenario, promotions: true, leaverShare: 0.4 }));
    for (const c of toCases(set)) {
      const events = Object.values(c.events ?? {});
      expect(events[0].type).toBe("hire");
      expect(events[0].date).toBe(c.employments?.[0].start_date);
      expect(c.employments?.[0].salary.amount).toMatch(/^\d+\.\d{2}$/);
      for (const e of events) {
        if (e.type === "appraisal") expect(e.date).toBe(`${e.year}-06-30`);
        if (e.type === "contract_change" && e.new_salary) expect(e.new_salary).toEqual({ amount: expect.stringMatching(/\.\d{2}$/), currency: "EUR" });
        expect(Object.keys(e).every((k) => k === k.toLowerCase())).toBe(true);
      }
      const dates = events.map((e) => e.date);
      expect(dates).toEqual([...dates].sort());
    }
  });
});

describe("the demo's pre-check refuses what load_case refuses", () => {
  const broken = JSON.parse(readFileSync(join(FIXTURE_DIR, "broken_demo_cases.json"), "utf8")) as {
    base: string;
    cases: { name: string; changes: Record<string, unknown>[]; error: string }[];
  };
  const baseFiles = () => {
    const files: Record<string, string> = {};
    for (const f of ["case.json", "cast.json", "storyline.json", "documents.json"]) {
      files[f] = lf(readFileSync(join(FIXTURE_DIR, broken.base, f), "utf8"));
    }
    return files;
  };

  it("the base case is clean", () => {
    expect(checkCase(readCaseFolder(baseFiles()))).toEqual([]);
  });

  it.each(broken.cases.map((b) => [b.name, b] as const))("%s", (_, b) => {
    const files = baseFiles();
    for (const change of b.changes) {
      const file = change.file as string;
      const data = JSON.parse(files[file]);
      if (change.rename) {
        const path = change.rename as string[];
        const parent = path.slice(0, -1).reduce((o, k) => o[k], data);
        const part = parent[path[path.length - 1]];
        delete parent[path[path.length - 1]];
        part.id = change.to;
        parent[change.to as string] = part;
      } else {
        const path = change.path as (string | number)[];
        const parent = path.slice(0, -1).reduce((o, k) => o[k], data);
        if (change.delete) delete parent[path[path.length - 1]];
        else parent[path[path.length - 1]] = change.value;
      }
      files[file] = JSON.stringify(data);
    }
    const problems = checkCase(readCaseFolder(files));
    expect(problems.join("\n")).toMatch(new RegExp(b.error));
  });
});

describe("documents and export read the saved cases", () => {
  it.each(RUNS)("%s: rendering from the cases gives the same documents and folders", (_, run) => {
    const set = run();
    const direct = expandDossiers(set);
    const stage = throughCases(set);
    expect(stage.read.problems).toEqual([]);
    expect(stage.pkg.caseIssues).toEqual([]);
    expect(stage.pkg.documents.map(plain)).toEqual(direct.documents.map(plain));
    expect(stage.pkg.folders).toEqual(direct.folders);
    expect(stage.pkg.documents.every((d) => d.caseDocId && d.caseEventId !== undefined)).toBe(true);
    expect(validate(stage.read.set, stage.pkg, { cases: stage.cases }).errors).toBe(0);
  });

  it("renders the bundled reference case 100101 as AMEXIO's 5 documents", () => {
    const stage = renderCases([referenceCase()], referenceRun());
    const example = expandDossiers(examplePreset()).documents.filter((d) => d.employeeId === "100101");
    expect(stage.read.problems).toEqual([]);
    expect(stage.pkg.documents.map(plain)).toEqual(example.map(plain));
    expect(stage.pkg.documents.map((d) => d.caseEventId)).toEqual(["EVT-001", null, "EVT-003", "EVT-004", "EVT-002"]);
  });

  it("a fact removed from the case shows up in the documents (no silent default)", () => {
    const c = referenceCase();
    delete c.personas!["P003"];
    c.events!["EVT-003"].participant_ids = ["P001"];
    const stage = renderCases([c], referenceRun());
    const medical = stage.pkg.documents.find((d) => d.docType === "medical_check")!;
    expect(medical.values.examiner).toBe("");
    const report = validate(stage.read.set, stage.pkg, { cases: [c] });
    expect(report.issues.some((i) => i.severity === "error" && /"Examined by" is empty/.test(i.message))).toBe(true);
  });

  it("when a case lists its documents, the case decides which exist", () => {
    const [c] = toCases(examplePreset());
    delete c.documents!["DOC-002"]; // no training certificate
    c.documents!["DOC-009"] = { ...c.documents!["DOC-005"], id: "DOC-009", metadata: { ...c.documents!["DOC-005"].metadata, document_date: "2026-08-31" } };
    const stage = renderCases([c], referenceRun());
    expect(stage.pkg.documents.map((d) => d.docType)).not.toContain("training_certificate");
    expect(stage.pkg.documents.find((d) => d.docType === "payslip")?.caseDocId).toBe("DOC-005");
    expect(stage.pkg.caseIssues).toEqual([
      { employeeId: "100101", message: expect.stringMatching(/^DOC-009 \(payslip, 2026-08-31\) cannot be rendered/) },
    ]);
    const report = validate(stage.read.set, stage.pkg, { cases: [c] });
    expect(report.issues.some((i) => i.code === "CASE" && /DOC-009/.test(i.message))).toBe(true);
  });

  it("puts the case folders and the ingest input in the ZIP under cases/", () => {
    const set = examplePreset();
    const files = caseExportFiles(throughCases(set), ingestInput(set));
    expect(Object.keys(files).sort()).toEqual(
      [
        ...["100101", "100102", "100103", "100104"].flatMap((n) =>
          ["case.json", "cast.json", "documents.json", "storyline.json"].map((f) => `cases/${n}/${f}`),
        ),
        "cases/employees.json",
        "cases/storylines.json",
      ].sort(),
    );
    const back = readCaseFiles(Object.fromEntries(Object.entries(files).map(([p, t]) => [p.slice(6), t])));
    expect(back).toEqual(toCases(set));
    expect(caseFolderFiles(back)).toEqual(caseFolderFiles(toCases(set)));
  });
});

describe("R2: the run as the case model's input", () => {
  it.each(RUNS)("%s: matches the input schemas", (_, run) => {
    const input = ingestInput(run());
    const employees = schemaValidator("input.employees.schema.json");
    const storylines = schemaValidator("input.storylines.schema.json");
    expect(employees(input.employees), JSON.stringify(employees.errors?.slice(0, 3))).toBe(true);
    expect(storylines(input.storylines), JSON.stringify(storylines.errors?.slice(0, 3))).toBe(true);
  });

  it("is AMEXIO's example input for the AMEXIO preset", () => {
    const input = ingestInput(examplePreset());
    const theirs = (name: string) => JSON.parse(readFileSync(join(FIXTURE_DIR, "generator", "amexio_example", name), "utf8"));
    expect(input.employees).toEqual(theirs("employees.json"));
    // Giulia's file lists the appraisal under "appraisals"; the demo writes it among the events (both accepted).
    const flat = (s: { storylines: { employeeId: string; events?: object[]; appraisals?: object[] }[] }) =>
      s.storylines.map((x) => ({
        employeeId: x.employeeId,
        events: [...(x.events ?? []), ...(x.appraisals ?? []).map((a) => ({ type: "appraisal", ...a }))],
      }));
    expect(flat(input.storylines)).toEqual(flat(theirs("storylines.json")));
  });
});

describe("checkCase", () => {
  it("lists every problem, not only the first", () => {
    const c: Case = referenceCase();
    c.events!["EVT-002"].date = "2020-01-01";
    c.events!["EVT-003"].participant_ids = ["P001", "P042"];
    expect(checkCase(c)).toEqual([
      "Event EVT-003 references unknown persona \"P042\".",
      "Event EVT-002 (training, 2020-01-01) happens before the hire on 2021-03-01.",
    ]);
  });
});
