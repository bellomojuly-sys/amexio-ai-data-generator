import { fullName } from "../model/dossier";
import { docType } from "../spec/doctypes";
import { xmlDate } from "../spec/format";
import type { DocumentInstance } from "../spec/types";
import { documentLocation } from "../generate/expand";
import type { DossierPackage, DossierSet } from "../generate/types";

/**
 * Writes import.xml for OpenText Object Importer in the shape of AMEXIO's
 * example: one <import> block; folders first, then documents, then updates.
 *
 * The XML is built by code from validated data, never written by the AI.
 * Text with &, < or > goes in CDATA (as the example does for "Health & Safety");
 * everything else is escaped.
 */

const SPECIAL = /[&<>]/;

export function xmlText(value: string): string {
  const clean = stripInvalidXmlChars(value);
  if (SPECIAL.test(clean) && !clean.includes("]]>")) return `<![CDATA[${clean}]]>`;
  return escapeText(clean);
}

export function escapeText(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function escapeAttr(value: string): string {
  return escapeText(stripInvalidXmlChars(value)).replace(/"/g, "&quot;");
}

/** XML 1.0 forbids most control characters, even escaped. */
export function stripInvalidXmlChars(value: string): string {
  // eslint-disable-next-line no-control-regex
  return value.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F￾￿]/g, "");
}

export function hasInvalidXmlChars(value: string): boolean {
  return stripInvalidXmlChars(value) !== value;
}

export function filePath(set: DossierSet, doc: DocumentInstance): string {
  const { basePath, packageName } = set.config.target;
  const base = basePath.endsWith("\\") ? basePath : `${basePath}\\`;
  return `${base}${packageName}\\files\\${doc.fileName}`;
}

function el(indent: string, name: string, text: string, attrs: Record<string, string> = {}): string {
  const a = Object.entries(attrs)
    .map(([k, v]) => ` ${k}="${escapeAttr(v)}"`)
    .join("");
  return `${indent}<${name}${a}>${xmlText(text)}</${name}>`;
}

export function documentNode(set: DossierSet, doc: DocumentInstance, indent = "  "): string[] {
  const t = set.config.target;
  const i2 = indent + "  ";
  const i3 = i2 + "  ";
  const spec = docType(doc.docType);
  const lines: string[] = [];
  lines.push(`${indent}<node type="document" action="${doc.action}">`);
  lines.push(el(i2, "location", documentLocation(set, doc.employeeId)));
  lines.push(el(i2, "title", doc.title, { language: "en" }));
  for (const [lang, title] of Object.entries(doc.extraTitles)) lines.push(el(i2, "title", title, { language: lang }));
  lines.push(el(i2, "description", doc.description, { language: "en" }));
  lines.push(el(i2, "file", filePath(set, doc)));
  lines.push(el(i2, "mime", t.mime));
  lines.push(el(i2, "created", xmlDate(doc.date)));
  lines.push(el(i2, "modified", xmlDate(doc.date)));
  lines.push(el(i2, "createby", t.createdBy));
  lines.push(el(i2, "owner", t.owner));
  if (doc.versionControl) {
    lines.push(el(i2, "versioncontrol", "TRUE"));
    lines.push(el(i2, "versiontype", doc.versionControl));
  }
  for (const acl of doc.acl) {
    const attrs: Record<string, string> = {};
    if (acl.group) attrs.group = acl.group;
    if (acl.standard) attrs.standard = acl.standard;
    attrs.permissions = acl.permissions;
    const a = Object.entries(attrs)
      .map(([k, v]) => ` ${k}="${escapeAttr(v)}"`)
      .join("");
    lines.push(`${i2}<acl${a}></acl>`);
  }
  const names = t.attributeNames;
  lines.push(`${i2}<category name="${escapeAttr(t.categoryName)}">`);
  lines.push(el(i3, "attribute", doc.employeeId, { name: names.employeeId }));
  lines.push(el(i3, "attribute", spec.documentType, { name: names.documentType }));
  lines.push(el(i3, "attribute", xmlDate(doc.date), { name: names.documentDate }));
  lines.push(el(i3, "attribute", doc.confidential ? "TRUE" : "FALSE", { name: names.confidential }));
  for (const tag of doc.tags) lines.push(el(i3, "attribute", tag, { name: names.tags }));
  lines.push(`${i2}</category>`);
  lines.push(`${indent}</node>`);
  return lines;
}

export function buildImportXml(set: DossierSet, pkg: DossierPackage): string {
  const out: string[] = [];
  const p = set.provenance;
  out.push(`<?xml version="1.0" encoding="UTF-8"?>`);
  out.push(`<!--`);
  out.push(`  SYNTHETIC DATA - made by the AMEXIO dossier generator demo. Not real people or records.`);
  out.push(`  Generation ${set.generationId}, seed ${set.config.seed}, as of ${set.config.asOf}.`);
  if (p.personas) out.push(`  Personas: ${sanitizeComment(p.personas)}. Storylines: ${sanitizeComment(p.storylines ?? "-")}.`);
  out.push(`  Object Importer control file: folders first, then documents, then updates.`);
  out.push(`  Dates are YYYYMMDD. Users, groups and categories must already exist in Content Server.`);
  out.push(`-->`);
  out.push(`<import>`);
  out.push(``);
  out.push(`  <!-- ============ STEP 1: create the folders ============ -->`);
  out.push(``);
  for (const f of pkg.folders) {
    out.push(`  <node type="folder" action="${set.config.importOptions.action}">`);
    out.push(el("    ", "location", f.location));
    out.push(el("    ", "title", f.title, { language: "en" }));
    out.push(el("    ", "description", f.description, { language: "en" }));
    out.push(`  </node>`);
  }
  out.push(``);
  out.push(`  <!-- ============ STEP 2: import the documents with their metadata ============ -->`);
  let current = "";
  for (const doc of pkg.documents) {
    if (doc.employeeId !== current) {
      current = doc.employeeId;
      const e = set.employees.find((x) => x.id === current);
      out.push(``);
      out.push(`  <!-- Employee ${current} ${e ? sanitizeComment(fullName(e)) : ""} -->`);
    }
    out.push(...documentNode(set, doc));
  }
  if (pkg.updates.length > 0) {
    out.push(``);
    out.push(`  <!-- ============ STEP 3: change something that already exists ============ -->`);
    out.push(``);
    for (const u of pkg.updates) {
      out.push(`  <node type="document" action="update">`);
      out.push(el("    ", "location", u.location));
      out.push(el("    ", "title", u.title, { language: "en" }));
      out.push(el("    ", "description", u.description, { language: "en" }));
      out.push(`  </node>`);
    }
  }
  out.push(``);
  out.push(`</import>`);
  out.push(``);
  return out.join("\n");
}

function sanitizeComment(s: string): string {
  return stripInvalidXmlChars(s).replace(/--/g, "- -");
}
