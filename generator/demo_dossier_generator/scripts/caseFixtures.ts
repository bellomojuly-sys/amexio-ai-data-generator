/**
 * The demo's cases as fixtures for the case model's tests (CI).
 *
 *   npm run fixtures     rewrite case_model/fixtures/demo_cases/ and
 *                        case_model/fixtures/generator/demo_* (scripts/write-case-fixtures.ts)
 *
 * demo_cases/<scenario>/<number>/   case folders as the demo writes them:
 *                                   case_model/test_demo_cases.py runs load_case on each
 * generator/demo_<scenario>/        the same runs as ingest input (R2, R3):
 *                                   case_model/test_fixtures.py ingests them
 *
 * Everything here is reproducible from the seed, without a model.
 * tests/case.test.ts fails when the committed fixtures are out of date.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { caseExportFiles, ingestInput, throughCases } from "../src/case/bridge";
import { cloneConfig, DEFAULT_CONFIG } from "../src/generate/config";
import { examplePreset } from "../src/generate/examplePreset";
import { generateOffline } from "../src/generate/offline";
import type { DossierSet } from "../src/generate/types";
import { CASE_MODEL_DIR } from "./caseTypes";

export const FIXTURE_DIR = join(CASE_MODEL_DIR, "fixtures");

interface Scenario {
  name: string;
  summary: string;
  set(): DossierSet;
  /** Also write the run as ingest input in fixtures/generator/demo_<name>/. */
  input: boolean;
}

export const SCENARIOS: Scenario[] = [
  {
    name: "amexio_example",
    summary: "AMEXIO's four employees and 20 documents (the demo's AMEXIO preset). Input: fixtures/generator/amexio_example.",
    set: () => examplePreset(),
    input: false,
  },
  {
    name: "small_company",
    summary: "No-AI run, seed 2026: 8 employees, 2 years of history, all 9 document types. Two leavers, a temporary contract made permanent (100108), promotions, sick leave, part time.",
    set: () => {
      const c = cloneConfig(DEFAULT_CONFIG);
      c.seed = 2026;
      c.employeeCount = 8;
      c.historyYears = 2;
      return generateOffline(c);
    },
    input: true,
  },
  {
    name: "leavers",
    summary: "No-AI run, seed 7: 6 employees, 1 year of history. Three leave (two at the end of a temporary contract), most have sick leave, some work part time.",
    set: () => {
      const c = cloneConfig(DEFAULT_CONFIG);
      c.seed = 7;
      c.employeeCount = 6;
      c.historyYears = 1;
      c.departments = ["Logistics", "Customer Service"];
      c.scenario = { ...c.scenario, leaverShare: 0.5, temporaryShare: 0.5, partTimeShare: 0.5, absenceShare: 0.8 };
      return generateOffline(c);
    },
    input: true,
  },
];

/** Every fixture file, by path relative to case_model/fixtures/. */
export function renderFixtures(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const s of SCENARIOS) {
    const set = s.set();
    const stage = throughCases(set);
    const files = caseExportFiles(stage, s.input ? ingestInput(set) : undefined);
    for (const [path, text] of Object.entries(files)) {
      const rest = path.slice("cases/".length);
      if (rest === "employees.json" || rest === "storylines.json") out[`generator/demo_${s.name}/${rest}`] = text;
      else out[`demo_cases/${s.name}/${rest}`] = text;
    }
  }
  out["demo_cases/README.md"] = [
    "# Demo cases",
    "",
    "Case folders written by the dossier generator demo (`generator/demo_dossier_generator`,",
    "`src/case/toCase.ts`), one folder per employee, in the four files of `save_case`.",
    "`test_demo_cases.py` loads every one with `load_case`, so a change on either side that",
    "breaks the shared format fails CI.",
    "",
    "Do not edit by hand. Regenerate from the demo with `npm run fixtures`.",
    "",
    "| Scenario | What it covers |",
    "| --- | --- |",
    ...SCENARIOS.map((s) => `| \`${s.name}\` | ${s.summary} |`),
    "",
  ].join("\n");
  return out;
}

/** The fixture files on disk that this script owns. */
export function committedFixtures(): Record<string, string> {
  const out: Record<string, string> = {};
  const walk = (dir: string) => {
    for (const name of readdirSync(dir)) {
      const full = join(dir, name);
      if (statSync(full).isDirectory()) walk(full);
      else out[relative(FIXTURE_DIR, full).split("\\").join("/")] = readFileSync(full, "utf8").replace(/\r\n/g, "\n");
    }
  };
  const demoCases = join(FIXTURE_DIR, "demo_cases");
  try {
    walk(demoCases);
  } catch {
    /* not written yet */
  }
  for (const s of SCENARIOS.filter((x) => x.input)) {
    try {
      walk(join(FIXTURE_DIR, "generator", `demo_${s.name}`));
    } catch {
      /* not written yet */
    }
  }
  return out;
}
