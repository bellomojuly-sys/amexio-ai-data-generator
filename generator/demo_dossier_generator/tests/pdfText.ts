import { unzlibSync } from "fflate";

/**
 * Reads the text out of AMEXIO's mock PDFs, so the golden test can compare
 * against the original files instead of a committed copy of their text.
 *
 * The mock PDFs were made with ReportLab: one content stream, encoded as
 * ASCII85 then Flate, with each piece of text drawn by a "(...) Tj" operator.
 * This reader handles exactly that, and tolerates Windows line endings that a
 * git checkout may have added to the files.
 */

function ascii85Decode(input: string): Uint8Array {
  const data = input.replace(/\s+/g, "").replace(/~>$/, "");
  const out: number[] = [];
  let group: number[] = [];
  for (const ch of data) {
    if (ch === "z" && group.length === 0) {
      out.push(0, 0, 0, 0);
      continue;
    }
    group.push(ch.charCodeAt(0) - 33);
    if (group.length === 5) {
      let value = 0;
      for (const d of group) value = value * 85 + d;
      out.push((value >>> 24) & 255, (value >>> 16) & 255, (value >>> 8) & 255, value & 255);
      group = [];
    }
  }
  if (group.length > 0) {
    const n = group.length;
    while (group.length < 5) group.push(84);
    let value = 0;
    for (const d of group) value = value * 85 + d;
    const bytes = [(value >>> 24) & 255, (value >>> 16) & 255, (value >>> 8) & 255, value & 255];
    out.push(...bytes.slice(0, n - 1));
  }
  return Uint8Array.from(out);
}

/** The strings drawn with Tj, in drawing order. */
function tjStrings(content: string): string[] {
  const out: string[] = [];
  for (let i = 0; i < content.length; i++) {
    if (content[i] !== "(") continue;
    let depth = 1;
    let s = "";
    let j = i + 1;
    for (; j < content.length && depth > 0; j++) {
      const c = content[j];
      if (c === "\\") {
        const next = content[j + 1];
        if (/[0-7]/.test(next)) {
          const oct = /^[0-7]{1,3}/.exec(content.slice(j + 1))![0];
          s += String.fromCharCode(parseInt(oct, 8));
          j += oct.length;
        } else {
          s += next === "n" ? "\n" : next === "r" ? "\r" : next === "t" ? "\t" : next;
          j += 1;
        }
        continue;
      }
      if (c === "(") depth++;
      if (c === ")") depth--;
      if (depth > 0) s += c;
    }
    if (/^\s*Tj/.test(content.slice(j))) out.push(s);
    i = j - 1;
  }
  return out;
}

/** Bytes to a string, one character per byte (true Latin-1, unlike TextDecoder's windows-1252). */
function latin1(bytes: Uint8Array): string {
  let s = "";
  for (let i = 0; i < bytes.length; i += 8192) s += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return s;
}

export function extractPdfText(pdf: Uint8Array): string[] {
  const raw = latin1(pdf);
  const strings: string[] = [];
  const streamRe = /<<([^]*?)>>\s*stream\r?\n([^]*?)\r?\n?endstream/g;
  let m: RegExpExecArray | null;
  while ((m = streamRe.exec(raw))) {
    const dict = m[1];
    let bytes = Uint8Array.from(m[2], (c) => c.charCodeAt(0));
    if (/ASCII85Decode/.test(dict)) bytes = ascii85Decode(m[2]);
    if (/FlateDecode/.test(dict)) bytes = unzlibSync(bytes);
    strings.push(...tjStrings(latin1(bytes)));
  }
  return strings;
}
