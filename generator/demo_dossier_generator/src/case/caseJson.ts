import type { Case } from "./generated/case";

/**
 * Case folders, byte for byte as the case model writes them.
 *
 * `save_case` in case_model/storage.py writes four files per case with
 * `json.dumps(indent=2, sort_keys=True, ensure_ascii=False) + "\n"`. This
 * module writes the same bytes from TypeScript, so a case folder made by the
 * demo and one made by `python -m case_model.ingest` can be compared with diff,
 * and reads them back into one Case object.
 */

export const CASE_FILES = ["case.json", "cast.json", "storyline.json", "documents.json"] as const;
export type CaseFileName = (typeof CASE_FILES)[number];
export type CaseFolder = Record<CaseFileName, string>;

/** Fields the case model stores as Python floats: they print as 40.0, not 40. */
const FLOAT_KEYS = new Set(["hours", "new_hours"]);
const FLOAT_MARK = "\u0000float:";

function pyFloat(n: number): string {
  return Number.isInteger(n) ? n.toFixed(1) : String(n);
}

function prepare(value: unknown, key?: string): unknown {
  if (typeof value === "number" && key && FLOAT_KEYS.has(key)) return FLOAT_MARK + pyFloat(value);
  if (Array.isArray(value)) return value.map((v) => prepare(v));
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const k of Object.keys(value).sort()) out[k] = prepare((value as Record<string, unknown>)[k], k);
    return out;
  }
  return value;
}

/** Python's `json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"`. */
export function pyJson(value: unknown): string {
  const text = JSON.stringify(prepare(value), null, 2);
  return text.replace(/"\\u0000float:([^"]*)"/g, "$1") + "\n";
}

/** The four files of one case folder (save_case). */
export function caseFolder(c: Case): CaseFolder {
  return {
    "case.json": pyJson({ case_number: c.case_number, dossier: c.dossier }),
    "cast.json": pyJson({ personas: c.personas ?? {}, organisations: c.organisations ?? {}, employments: c.employments ?? [] }),
    "storyline.json": pyJson({ events: c.events ?? {} }),
    "documents.json": pyJson({ documents: c.documents ?? {} }),
  };
}

/** Every case as `{prefix}{case_number}/{file}` paths, ready for a ZIP. */
export function caseFolderFiles(cases: Case[], prefix = ""): Record<string, string> {
  const files: Record<string, string> = {};
  for (const c of cases) {
    for (const [name, text] of Object.entries(caseFolder(c))) files[`${prefix}${c.case_number}/${name}`] = text;
  }
  return files;
}

export class CaseReadError extends Error {}

function parse(text: string, name: string): Record<string, unknown> {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch (e) {
    throw new CaseReadError(`${name} is not valid JSON (${(e as Error).message}).`);
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new CaseReadError(`${name} must hold a JSON object.`);
  return value as Record<string, unknown>;
}

/** Reads a case folder back into one Case (load_case, without the rule checks: see checkCase). */
export function readCaseFolder(files: Partial<Record<string, string>>, where = "case folder"): Case {
  const missing = CASE_FILES.filter((f) => typeof files[f] !== "string");
  if (missing.length) throw new CaseReadError(`${where}: missing ${missing.join(", ")}.`);
  const head = parse(files["case.json"]!, `${where}/case.json`);
  const cast = parse(files["cast.json"]!, `${where}/cast.json`);
  const storyline = parse(files["storyline.json"]!, `${where}/storyline.json`);
  const documents = parse(files["documents.json"]!, `${where}/documents.json`);
  return withDefaults({
    case_number: head.case_number,
    dossier: head.dossier,
    personas: cast.personas,
    organisations: cast.organisations,
    employments: cast.employments,
    events: storyline.events,
    documents: documents.documents,
  } as Case);
}

const EVENT_DEFAULTS: Record<string, Record<string, null>> = {
  hire: {},
  contract_change: { new_salary: null, new_position: null, new_contract_type: null, new_hours: null },
  training: {},
  appraisal: { comment: null },
  medical_check: {},
  absence: { end_date: null },
  termination: { notice_date: null },
};

/**
 * Fills in the optional fields the way pydantic does when it loads a case, so
 * a folder written by hand (or by an older version) reads into the same
 * object as one written by save_case.
 */
export function withDefaults(c: Case): Case {
  const personas = Object.fromEntries(
    Object.entries(c.personas ?? {}).map(([k, p]) => [
      k,
      { address: null, date_of_birth: null, organisation_id: null, salutation: null, ...p },
    ]),
  );
  const organisations = Object.fromEntries(
    Object.entries(c.organisations ?? {}).map(([k, o]) => [k, { address: null, kind: null, ...o }]),
  );
  const events = Object.fromEntries(
    Object.entries(c.events ?? {}).map(([k, e]) => [
      k,
      { label: null, summary: null, ...(EVENT_DEFAULTS[e?.type] ?? {}), ...e },
    ]),
  ) as Case["events"];
  const documents = Object.fromEntries(
    Object.entries(c.documents ?? {}).map(([k, d]) => [
      k,
      { event_id: null, text: null, ...d, metadata: { tags: [], ...d?.metadata } },
    ]),
  ) as Case["documents"];
  return {
    case_number: c.case_number,
    dossier: { description: null, folder_title: null, ...c.dossier },
    personas,
    organisations,
    employments: c.employments ?? [],
    events,
    documents,
  };
}

/** The four files joined into one object, as in case_model/reference_dossier.golden.json. */
export function caseJson(c: Case): string {
  return pyJson(c);
}
