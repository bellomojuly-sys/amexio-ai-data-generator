import { isISODate, yearOf } from "../model/dates";
import type { Employee } from "../model/dossier";
import { fullName, MEDICAL_RESULTS, RATINGS } from "../model/dossier";
import { buildTimeline } from "../model/timeline";
import { docType } from "../spec/doctypes";
import { renderDocument, renderedLines } from "../spec/render";
import { netSalary, nextMedicalCheck, payDate, wageTax } from "../spec/rules";
import type { DocumentInstance } from "../spec/types";
import { employeeFolderTitle } from "../generate/expand";
import type { DossierPackage, DossierSet } from "../generate/types";
import { hasInvalidXmlChars } from "../export/importXml";
import { nonWinAnsiChars } from "../export/winansi";
import { checkCase } from "../case/checkCase";
import type { Case } from "../case/generated/case";

/**
 * Step 5: deterministic checks. No AI judges AI output here: every check is
 * plain code comparing documents with each other, with the source facts and
 * with what the target system accepts. Any error blocks the export.
 */

export type Severity = "error" | "warning" | "info";
export type CheckKind = "case model" | "format" | "relationships" | "timeline" | "consistency" | "target system" | "privacy";

export interface Issue {
  check: string;
  code: string;
  severity: Severity;
  message: string;
  employeeId?: string;
  docKey?: string;
}

export interface CheckResult {
  code: string;
  title: string;
  description: string;
  kind: CheckKind;
  issues: Issue[];
  /** How many things were checked, for "142 payslips checked". */
  checked: number;
}

export interface ValidationReport {
  checks: CheckResult[];
  issues: Issue[];
  errors: number;
  warnings: number;
  infos: number;
}

interface Ctx {
  set: DossierSet;
  pkg: DossierPackage;
  employees: Map<string, Employee>;
  docsByEmployee: Map<string, DocumentInstance[]>;
  xml?: string;
  parseXml?: (xml: string) => string | null;
  cases?: Case[];
}

interface CheckDef {
  code: string;
  title: string;
  description: string;
  kind: CheckKind;
  run(ctx: Ctx, add: (severity: Severity, message: string, ref?: { employeeId?: string; docKey?: string }) => void): number;
}

const SAFE_FILENAME = /^[A-Za-z0-9_.-]+$/;
const MEDICAL_WORDS = /diagnos|illness|disease|burn-?out|depress|cancer|pregnan|surgery|therapy|medication|disorder|injur/i;

function docLabel(ctx: Ctx, d: DocumentInstance): string {
  const e = ctx.employees.get(d.employeeId);
  return `${d.title} (${e ? `${e.id} ${fullName(e)}` : d.employeeId})`;
}

function num(v: unknown): number {
  return typeof v === "number" ? v : Number(v);
}

const CHECKS: CheckDef[] = [
  {
    code: "CASE",
    title: "Every dossier is a valid case",
    description:
      "The saved cases follow the case model's rules (the ones load_case applies): well-formed IDs, every reference points at a part the case holds, one hire on the start date, nothing before the hire or after the last working day, and every document except payslips and annual statements points at the event it records. Every document a case lists is rendered.",
    kind: "case model",
    run(ctx, add) {
      if (!ctx.cases) return 0;
      for (const c of ctx.cases) {
        for (const message of checkCase(c)) add("error", `Case ${c.case_number}: ${message}`, { employeeId: c.case_number });
      }
      for (const i of ctx.pkg.caseIssues ?? []) add("error", `Case ${i.employeeId}: ${i.message}`, { employeeId: i.employeeId });
      return ctx.cases.length;
    },
  },
  {
    code: "FIELDS",
    title: "Every field is filled in and well formed",
    description: "Required fields present; dates are real dates; amounts are whole positive euros; ratings and results come from the allowed lists.",
    kind: "format",
    run(ctx, add) {
      for (const d of ctx.pkg.documents) {
        const spec = docType(d.docType);
        for (const f of spec.fields) {
          const v = d.values[f.key];
          if (v === undefined || v === "") {
            if (!f.optional) add("error", `${docLabel(ctx, d)}: "${f.label}" is empty.`, { employeeId: d.employeeId, docKey: d.key });
            continue;
          }
          if ((f.format === "date" || f.format === "monthYear") && typeof v === "string" && !isISODate(v) && v !== "Not yet returned") {
            add("error", `${docLabel(ctx, d)}: "${f.label}" is not a valid date (${v}).`, { employeeId: d.employeeId, docKey: d.key });
          }
          if ((f.format === "eurGrouped" || f.format === "eurPlain") && (!Number.isInteger(num(v)) || num(v) <= 0)) {
            add("error", `${docLabel(ctx, d)}: "${f.label}" must be a whole positive amount (${String(v)}).`, { employeeId: d.employeeId, docKey: d.key });
          }
        }
        if (d.docType === "performance_appraisal" && !RATINGS.includes(String(d.values.rating) as never)) {
          add("error", `${docLabel(ctx, d)}: rating "${String(d.values.rating)}" is not allowed.`, { employeeId: d.employeeId, docKey: d.key });
        }
        if (d.docType === "medical_check" && !MEDICAL_RESULTS.includes(String(d.values.result) as never)) {
          add("error", `${docLabel(ctx, d)}: result "${String(d.values.result)}" is not an allowed fitness conclusion.`, { employeeId: d.employeeId, docKey: d.key });
        }
      }
      return ctx.pkg.documents.length;
    },
  },
  {
    code: "IDENTITY",
    title: "Each document belongs to exactly one employee",
    description: "Employee ID is the same in the file name, the folder, the metadata and the PDF header; every employee has a folder.",
    kind: "relationships",
    run(ctx, add) {
      const folderTitles = new Set(ctx.pkg.folders.map((f) => f.title));
      for (const e of ctx.set.employees) {
        if (!folderTitles.has(employeeFolderTitle(e))) add("error", `${e.id} ${fullName(e)} has no folder.`, { employeeId: e.id });
      }
      for (const d of ctx.pkg.documents) {
        if (!ctx.employees.has(d.employeeId)) {
          add("error", `${d.fileName}: employee ${d.employeeId} does not exist.`, { docKey: d.key });
          continue;
        }
        if (!d.fileName.startsWith(`${d.employeeId}_`) || !d.fileName.endsWith(".pdf")) {
          add("error", `${d.fileName}: file name does not start with the employee ID ${d.employeeId}.`, { employeeId: d.employeeId, docKey: d.key });
        }
        if (!SAFE_FILENAME.test(d.fileName)) {
          add("error", `${d.fileName}: file name has characters outside A-Z, 0-9, _ . -`, { employeeId: d.employeeId, docKey: d.key });
        }
      }
      return ctx.pkg.documents.length;
    },
  },
  {
    code: "UNIQUE",
    title: "File names and titles are unique",
    description: "No two files share a name; no two documents in one folder share a title (Content Server needs unique names in a folder).",
    kind: "target system",
    run(ctx, add) {
      const files = new Map<string, DocumentInstance>();
      for (const d of ctx.pkg.documents) {
        const prev = files.get(d.fileName.toLowerCase());
        if (prev) add("error", `Two documents use the file name ${d.fileName}.`, { employeeId: d.employeeId, docKey: d.key });
        files.set(d.fileName.toLowerCase(), d);
      }
      for (const [employeeId, docs] of ctx.docsByEmployee) {
        const titles = new Map<string, DocumentInstance>();
        for (const d of docs) {
          const prev = titles.get(d.title.toLowerCase());
          if (prev) add("error", `Folder ${employeeId}: "${d.title}" is used by two documents (${prev.fileName} and ${d.fileName}).`, { employeeId, docKey: d.key });
          titles.set(d.title.toLowerCase(), d);
        }
      }
      return ctx.pkg.documents.length;
    },
  },
  {
    code: "TARGET",
    title: "Only names that exist in Content Server",
    description: "Category, attribute names, users and groups must already exist: the import never creates them. Document types outside AMEXIO's example are flagged.",
    kind: "target system",
    run(ctx, add) {
      const t = ctx.set.config.target;
      if (!t.knownCategories.includes(t.categoryName)) add("error", `Category "${t.categoryName}" is not a known category.`);
      for (const u of new Set([t.createdBy, t.owner])) {
        if (!t.knownUsers.includes(u)) add("error", `User "${u}" is not a known Content Server user.`);
      }
      const reportedTypes = new Set<string>();
      for (const d of ctx.pkg.documents) {
        for (const acl of d.acl) {
          if (acl.group && !t.knownGroups.includes(acl.group)) {
            add("error", `${docLabel(ctx, d)}: group "${acl.group}" does not exist in Content Server.`, { employeeId: d.employeeId, docKey: d.key });
          }
          if (acl.standard && !t.knownStandardAcls.includes(acl.standard)) {
            add("error", `${docLabel(ctx, d)}: standard ACL "${acl.standard}" is unknown.`, { employeeId: d.employeeId, docKey: d.key });
          }
          if (!/^[01]{9}$/.test(acl.permissions)) {
            add("error", `${docLabel(ctx, d)}: permissions "${acl.permissions}" must be nine 0/1 switches.`, { employeeId: d.employeeId, docKey: d.key });
          }
        }
        const type = docType(d.docType).documentType;
        if (!t.knownDocumentTypes.includes(type) && !reportedTypes.has(type)) {
          reportedTypes.add(type);
          const n = ctx.pkg.documents.filter((x) => x.docType === d.docType).length;
          add("warning", `Document Type "${type}" (${n} documents) is not in AMEXIO's example. Confirm it exists before importing.`);
        }
      }
      return ctx.pkg.documents.length;
    },
  },
  {
    code: "TIMELINE",
    title: "Everything happens while the person works here",
    description: "No document before the start date or after the as-of date; nothing after the last working day except the annual income statement.",
    kind: "timeline",
    run(ctx, add) {
      for (const d of ctx.pkg.documents) {
        const e = ctx.employees.get(d.employeeId);
        if (!e) continue;
        const end = ctx.set.storylines[e.id]?.events.find((x) => x.type === "termination");
        if (d.date < e.hireDate) add("error", `${docLabel(ctx, d)} is dated ${d.date}, before the start date ${e.hireDate}.`, { employeeId: e.id, docKey: d.key });
        if (d.date > ctx.set.config.asOf) add("error", `${docLabel(ctx, d)} is dated ${d.date}, after the as-of date ${ctx.set.config.asOf}.`, { employeeId: e.id, docKey: d.key });
        if (end && d.date > end.date && d.docType !== "annual_income_statement") {
          add("error", `${docLabel(ctx, d)} is dated ${d.date}, after the last working day ${end.date}.`, { employeeId: e.id, docKey: d.key });
        }
      }
      return ctx.pkg.documents.length;
    },
  },
  {
    code: "DATES",
    title: "One date per document, everywhere",
    description: "The date printed in the PDF equals <created>, <modified> and the Document Date attribute.",
    kind: "consistency",
    run(ctx, add) {
      let n = 0;
      for (const d of ctx.pkg.documents) {
        const field = docType(d.docType).dateField;
        if (!field) continue;
        n++;
        const printed = d.values[field];
        if (typeof printed === "string" && printed !== d.date) {
          add("error", `${docLabel(ctx, d)}: the PDF says ${printed} but the metadata says ${d.date}.`, { employeeId: d.employeeId, docKey: d.key });
        }
      }
      return n;
    },
  },
  {
    code: "PAY",
    title: "Payslips match the contract",
    description: "Gross pay on each payslip equals the salary in the contract or latest amendment in force on the payment date.",
    kind: "consistency",
    run(ctx, add) {
      let n = 0;
      for (const [employeeId, docs] of ctx.docsByEmployee) {
        const contracts = docs
          .filter((d) => d.docType === "employment_contract" || d.docType === "contract_amendment")
          .map((d) => ({ date: d.date, salary: num(d.values.salary), doc: d }))
          .sort((a, b) => a.date.localeCompare(b.date));
        if (contracts.length === 0) continue;
        for (const p of docs.filter((d) => d.docType === "payslip")) {
          n++;
          const inForce = [...contracts].reverse().find((c) => c.date <= p.date);
          if (!inForce) continue;
          if (num(p.values.gross) !== inForce.salary) {
            add(
              "error",
              `${docLabel(ctx, p)} shows EUR ${num(p.values.gross)} gross, but "${inForce.doc.title}" sets the salary at EUR ${inForce.salary}.`,
              { employeeId, docKey: p.key },
            );
          }
        }
      }
      return n;
    },
  },
  {
    code: "PAYROLL",
    title: "Payroll sums add up",
    description: "Wage tax is 37% of gross (rounded half to even), net = gross - tax, and each annual statement equals that year's payslips.",
    kind: "consistency",
    run(ctx, add) {
      let n = 0;
      for (const d of ctx.pkg.documents.filter((x) => x.docType === "payslip")) {
        n++;
        const gross = num(d.values.gross);
        if (num(d.values.tax) !== wageTax(gross)) add("error", `${docLabel(ctx, d)}: wage tax should be EUR ${wageTax(gross)}, not EUR ${num(d.values.tax)}.`, { employeeId: d.employeeId, docKey: d.key });
        if (num(d.values.net) !== gross - num(d.values.tax)) add("error", `${docLabel(ctx, d)}: net pay should be gross minus tax.`, { employeeId: d.employeeId, docKey: d.key });
      }
      for (const s of ctx.pkg.documents.filter((x) => x.docType === "annual_income_statement")) {
        n++;
        const e = ctx.employees.get(s.employeeId)!;
        const year = num(s.values.year);
        const timeline = buildTimeline(e, ctx.set.storylines[e.id]);
        const payslips = (ctx.docsByEmployee.get(e.id) ?? []).filter((d) => d.docType === "payslip" && yearOf(d.date) === year);
        let expected = { gross: 0, tax: 0, net: 0, months: 0 };
        for (let m = 1; m <= 12; m++) {
          const pd = payDate(year, m);
          if (!timeline.employedOn(pd)) continue;
          const g = timeline.stateAt(pd).salary;
          expected = { gross: expected.gross + g, tax: expected.tax + wageTax(g), net: expected.net + netSalary(g), months: expected.months + 1 };
        }
        // When all of that year's payslips are in the package, compare with the documents themselves.
        if (payslips.length === expected.months) {
          expected = payslips.reduce(
            (a, p) => ({ gross: a.gross + num(p.values.gross), tax: a.tax + num(p.values.tax), net: a.net + num(p.values.net), months: a.months + 1 }),
            { gross: 0, tax: 0, net: 0, months: 0 },
          );
        }
        if (num(s.values.gross) !== expected.gross || num(s.values.tax) !== expected.tax || num(s.values.net) !== expected.net) {
          add(
            "error",
            `${docLabel(ctx, s)}: totals (EUR ${num(s.values.gross)} gross) do not match the ${expected.months} payslips of ${year} (EUR ${expected.gross} gross).`,
            { employeeId: e.id, docKey: s.key },
          );
        }
      }
      return n;
    },
  },
  {
    code: "MEDICAL",
    title: "Medical checks follow the 2-year rhythm",
    description: "'Next check' = examination date + 2 years; a follow-up check is held on that date.",
    kind: "consistency",
    run(ctx, add) {
      let n = 0;
      for (const [employeeId, docs] of ctx.docsByEmployee) {
        const checks = docs.filter((d) => d.docType === "medical_check").sort((a, b) => a.date.localeCompare(b.date));
        checks.forEach((c, i) => {
          n++;
          const exam = String(c.values.examDate);
          if (c.values.nextCheck !== nextMedicalCheck(exam)) {
            add("error", `${docLabel(ctx, c)}: next check should be ${nextMedicalCheck(exam)}.`, { employeeId, docKey: c.key });
          }
          const prev = checks[i - 1];
          if (prev && prev.values.nextCheck !== c.values.examDate) {
            add("warning", `${docLabel(ctx, c)} is held on ${exam}, but the previous check planned it for ${String(prev.values.nextCheck)}.`, { employeeId, docKey: c.key });
          }
        });
      }
      return n;
    },
  },
  {
    code: "APPRAISAL",
    title: "Appraisals have a real manager",
    description: "The manager on an appraisal is not the employee and was employed on the review date; review date = end of review period.",
    kind: "relationships",
    run(ctx, add) {
      let n = 0;
      for (const d of ctx.pkg.documents.filter((x) => x.docType === "performance_appraisal")) {
        n++;
        const period = d.values.reviewPeriod;
        if (typeof period === "object" && period.to !== d.values.reviewDate) {
          add("error", `${docLabel(ctx, d)}: review date is not the end of the review period.`, { employeeId: d.employeeId, docKey: d.key });
        }
        const managerId = d.meta.managerId;
        if (!managerId) continue;
        if (managerId === d.employeeId) {
          add("error", `${docLabel(ctx, d)}: the employee is listed as their own manager.`, { employeeId: d.employeeId, docKey: d.key });
          continue;
        }
        const m = ctx.employees.get(managerId);
        if (!m) {
          add("error", `${docLabel(ctx, d)}: manager ${managerId} does not exist.`, { employeeId: d.employeeId, docKey: d.key });
          continue;
        }
        const t = buildTimeline(m, ctx.set.storylines[m.id]);
        if (!t.employedOn(d.date)) {
          add("error", `${docLabel(ctx, d)}: manager ${fullName(m)} was not employed on ${d.date}.`, { employeeId: d.employeeId, docKey: d.key });
        }
      }
      return n;
    },
  },
  {
    code: "FOLDER",
    title: "Folder descriptions match the latest contract",
    description: "The position in each folder description is the one in the employee's latest contract or amendment.",
    kind: "consistency",
    run(ctx, add) {
      let n = 0;
      for (const f of ctx.pkg.folders) {
        if (!f.employeeId) continue;
        const docs = ctx.docsByEmployee.get(f.employeeId) ?? [];
        const latest = docs
          .filter((d) => d.docType === "employment_contract" || d.docType === "contract_amendment")
          .sort((a, b) => a.date.localeCompare(b.date))
          .pop();
        if (!latest) continue;
        n++;
        if (!f.description.includes(`, ${String(latest.values.position)} (`)) {
          add("error", `Folder ${f.title}: description says "${f.description}", but the latest contract says ${String(latest.values.position)}.`, { employeeId: f.employeeId });
        }
      }
      return n;
    },
  },
  {
    code: "PRINTABLE",
    title: "All text can be printed and imported",
    description: "Text in PDFs uses only characters the standard PDF font can print; XML text has no forbidden control characters.",
    kind: "target system",
    run(ctx, add) {
      for (const d of ctx.pkg.documents) {
        const e = ctx.employees.get(d.employeeId);
        if (!e) continue;
        const text = renderedLines(renderDocument(d, e, ctx.set.config.target)).join("\n");
        const bad = nonWinAnsiChars(text);
        if (bad.length) add("error", `${docLabel(ctx, d)}: cannot print ${bad.map((c) => `"${c}"`).join(", ")} with the standard PDF font.`, { employeeId: d.employeeId, docKey: d.key });
        const xmlText = [d.title, d.description, ...Object.values(d.extraTitles)].join("\n");
        if (hasInvalidXmlChars(xmlText)) add("error", `${docLabel(ctx, d)}: title or description contains characters XML does not allow.`, { employeeId: d.employeeId, docKey: d.key });
      }
      return ctx.pkg.documents.length;
    },
  },
  {
    code: "PRIVACY",
    title: "Medical information stays minimal and locked",
    description: "Medical and absence documents hold no diagnosis and are readable only by HR Medical; AI-written comments contain no numbers or health details.",
    kind: "privacy",
    run(ctx, add) {
      let n = 0;
      for (const d of ctx.pkg.documents) {
        if (d.docType === "medical_check" || d.docType === "absence_report") {
          n++;
          const medical = d.acl.find((a) => a.group === "HR Medical");
          const world = d.acl.find((a) => a.standard === "world");
          if (!medical || !world || /1/.test(world.permissions)) {
            add("error", `${docLabel(ctx, d)}: must be readable by HR Medical only (world gets no rights).`, { employeeId: d.employeeId, docKey: d.key });
          }
          const extra = Object.keys(d.values).filter((k) => !docType(d.docType).fields.some((f) => f.key === k));
          if (extra.length) add("error", `${docLabel(ctx, d)}: unexpected fields ${extra.join(", ")}.`, { employeeId: d.employeeId, docKey: d.key });
        }
        if (d.docType === "performance_appraisal" && typeof d.values.comment === "string") {
          n++;
          if (/\d/.test(d.values.comment)) add("error", `${docLabel(ctx, d)}: the AI comment contains numbers; facts must come from code.`, { employeeId: d.employeeId, docKey: d.key });
          if (MEDICAL_WORDS.test(d.values.comment)) add("error", `${docLabel(ctx, d)}: the AI comment mentions health details.`, { employeeId: d.employeeId, docKey: d.key });
        }
      }
      return n;
    },
  },
  {
    code: "XML",
    title: "import.xml is well-formed",
    description: "The generated control file parses as XML.",
    kind: "target system",
    run(ctx, add) {
      if (!ctx.xml || !ctx.parseXml) return 0;
      const error = ctx.parseXml(ctx.xml);
      if (error) add("error", `import.xml could not be parsed: ${error}`);
      return 1;
    },
  },
];

export function validate(
  set: DossierSet,
  pkg: DossierPackage,
  options: { xml?: string; parseXml?: (xml: string) => string | null; cases?: Case[] } = {},
): ValidationReport {
  const ctx: Ctx = {
    set,
    pkg,
    employees: new Map(set.employees.map((e) => [e.id, e])),
    docsByEmployee: new Map(),
    xml: options.xml,
    parseXml: options.parseXml,
    cases: options.cases,
  };
  for (const d of pkg.documents) {
    const list = ctx.docsByEmployee.get(d.employeeId) ?? [];
    list.push(d);
    ctx.docsByEmployee.set(d.employeeId, list);
  }
  const checks: CheckResult[] = CHECKS.map((c) => {
    const issues: Issue[] = [];
    const checked = c.run(ctx, (severity, message, ref) => issues.push({ check: c.code, code: c.code, severity, message, ...ref }));
    return { code: c.code, title: c.title, description: c.description, kind: c.kind, issues, checked };
  });
  const fixes = set.corrections.filter((c) => c.kind !== "rule");
  if (fixes.length) {
    checks.push({
      code: "AI_FIXES",
      title: "AI answers corrected by code",
      description: "Values the AI proposed outside the allowed ranges, fixed before any document was made.",
      kind: "format",
      checked: fixes.length,
      issues: [
        {
          check: "AI_FIXES",
          code: "AI_FIXES",
          severity: "info",
          message: `Code corrected ${fixes.length} value${fixes.length === 1 ? "" : "s"} in the AI's answers before making documents. See the Personas and Storylines steps.`,
        },
      ],
    });
  }
  const issues = checks.flatMap((c) => c.issues);
  return {
    checks,
    issues,
    errors: issues.filter((i) => i.severity === "error").length,
    warnings: issues.filter((i) => i.severity === "warning").length,
    infos: issues.filter((i) => i.severity === "info").length,
  };
}
