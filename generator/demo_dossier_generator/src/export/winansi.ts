/**
 * The PDFs use the standard Helvetica font, which only knows the WinAnsi
 * character set (roughly Latin-1). A name like "Şahin" or "Wałęsa" cannot be
 * printed without embedding another font. The validator flags such text so it
 * never silently turns into "?" in a PDF while import.xml has the real name.
 */

const EXTRA = new Set(
  Array.from("€‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ").map((c) => c.codePointAt(0)!),
);

export function isWinAnsiChar(code: number): boolean {
  if (code === 0x0a || code === 0x0d || code === 0x09) return true;
  if (code >= 0x20 && code <= 0x7e) return true;
  if (code >= 0xa0 && code <= 0xff) return true;
  return EXTRA.has(code);
}

export function nonWinAnsiChars(text: string): string[] {
  const bad = new Set<string>();
  for (const ch of text) {
    if (!isWinAnsiChar(ch.codePointAt(0)!)) bad.add(ch);
  }
  return [...bad];
}

export function toWinAnsi(text: string): string {
  let out = "";
  for (const ch of text) out += isWinAnsiChar(ch.codePointAt(0)!) ? ch : "?";
  return out;
}
