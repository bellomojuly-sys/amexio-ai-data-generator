/**
 * TypeScript types from the case model's JSON Schemas (R1), and the bundled
 * copy of the reference case 100101 (R6).
 *
 *   npm run types        regenerate src/case/generated/ (scripts/write-case-types.ts)
 *
 * The schemas and the golden case live in case_model/ and are owned by the
 * case model (python3 -m case_model.schema, python3 -m
 * case_model.reference_dossier). tests/case.test.ts fails when the committed
 * copies no longer match them, so a change there cannot slip by.
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { compile, type JSONSchema } from "json-schema-to-typescript";

const here = dirname(fileURLToPath(import.meta.url));
export const CASE_MODEL_DIR = join(here, "..", "..", "..", "case_model");
export const SCHEMA_DIR = join(CASE_MODEL_DIR, "schema");
export const GOLDEN_FILE = join(CASE_MODEL_DIR, "reference_dossier.golden.json");
export const OUT_DIR = join(here, "..", "src", "case", "generated");

const SCHEMAS: Record<string, { file: string; name: string }> = {
  "case.ts": { file: "case.schema.json", name: "Case" },
  "inputEmployees.ts": { file: "input.employees.schema.json", name: "EmployeesIn" },
  "inputStorylines.ts": { file: "input.storylines.schema.json", name: "StorylinesIn" },
};

export async function renderCaseTypes(): Promise<Record<string, string>> {
  const out: Record<string, string> = {};
  for (const [target, { file, name }] of Object.entries(SCHEMAS)) {
    const schema = JSON.parse(readFileSync(join(SCHEMA_DIR, file), "utf8")) as JSONSchema;
    out[target] = await compile(schema, name, {
      additionalProperties: false,
      unreachableDefinitions: true,
      format: false,
      bannerComment: `/* Generated from case_model/schema/${file} by \`npm run types\`. Do not edit. */`,
    });
  }
  // The reference case, so the app can render it without the Python side.
  out["reference100101.json"] = readFileSync(GOLDEN_FILE, "utf8").replace(/\r\n/g, "\n");
  return out;
}

export async function writeCaseTypes(): Promise<string[]> {
  const files = await renderCaseTypes();
  mkdirSync(OUT_DIR, { recursive: true });
  for (const [name, text] of Object.entries(files)) writeFileSync(join(OUT_DIR, name), text);
  return Object.keys(files);
}
