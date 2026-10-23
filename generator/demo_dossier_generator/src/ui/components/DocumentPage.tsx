import type { CSSProperties, ReactNode } from "react";
import type { RenderedDocument, RenderedRow } from "../../spec/types";

/**
 * The PDF page drawn in HTML, using the same coordinates as src/export/pdf.ts
 * (points on an A4 page, scaled to the container width).
 */

const W = 595.2756;
const H = 841.8898;
const LEFT = 56.6929;
const VALUE_X = 226.7717;
const RIGHT = 538.5827;

const u = (pt: number) => `calc(${pt} / ${W} * 100cqw)`;

function text(x: number, baselineY: number, size: number, extra: CSSProperties = {}): CSSProperties {
  return { left: u(x), top: u(H - baselineY - size * 0.8), fontSize: u(size), ...extra };
}

/** Rough wrap matching the PDF's: Helvetica averages about half an em per character. */
function approxWrap(value: string, size: number, width: number): string[] {
  const maxChars = Math.floor(width / (size * 0.5));
  const words = value.split(/\s+/);
  const lines: string[] = [];
  let line = "";
  for (const w of words) {
    const candidate = line ? `${line} ${w}` : w;
    if (candidate.length > maxChars && line) {
      lines.push(line);
      line = w;
    } else line = candidate;
  }
  if (line) lines.push(line);
  return lines.length ? lines : [""];
}

function Val({ row, children }: { row: RenderedRow; children: ReactNode }) {
  return <span className={`hl o-${row.origin}`}>{children}</span>;
}

export function DocumentPage({ doc, showOrigin }: { doc: RenderedDocument; showOrigin: boolean }) {
  let y = 615.1181;
  const rows = doc.rows.map((row) => {
    const lines = approxWrap(row.value, 12, RIGHT - VALUE_X);
    const top = y;
    y -= 22.6772 + (lines.length - 1) * 14.4;
    return { row, lines, top };
  });
  return (
    <div className="page-frame">
      <div className={`page ${showOrigin ? "show-origin" : ""}`} role="img" aria-label={`Preview of ${doc.title}`}>
        <div className="banner" />
        <span className="pt" style={text(0, 802.2047, 16, { left: 0, right: 0, textAlign: "center", fontWeight: 700, color: "var(--paper)" })}>
          {doc.banner}
        </span>
        <span className="pt" style={text(LEFT, 728.5039, 22, { fontWeight: 700 })}>
          {doc.title}
        </span>
        {doc.identity.map((row, i) => (
          <span key={row.fieldKey} className="pt" style={text(LEFT, 700.1575 - i * 19.8425, 12)}>
            {row.label}: <Val row={row}>{row.value}</Val>
          </span>
        ))}
        <div className="rule" style={{ left: u(LEFT), width: u(RIGHT - LEFT), top: u(H - 643.4646) }} />
        {rows.map(({ row, lines, top }) => (
          <div key={row.fieldKey}>
            <span className="pt" style={text(LEFT, top, 12, { fontWeight: 700 })}>
              {row.label}:
            </span>
            {lines.map((line, i) => (
              <span key={i} className="pt" style={text(VALUE_X, top - i * 14.4, 12)}>
                <Val row={row}>{line}</Val>
              </span>
            ))}
          </div>
        ))}
        <span className="pt" style={text(LEFT, 56.6929, 9, { fontStyle: "italic", color: "var(--paper-footer)" })}>
          {doc.footer}
        </span>
      </div>
    </div>
  );
}

export function OriginLegend({ fromAi }: { fromAi: boolean }) {
  return (
    <div className="legend">
      <span><i style={{ background: "var(--hl-ai)" }} />{fromAi ? "Proposed by the AI, checked by code" : "From the persona or storyline"}</span>
      <span><i style={{ background: "var(--hl-ai-text)" }} />Free text written by the AI</span>
      <span><i style={{ background: "var(--hl-rule)" }} />Calculated by code</span>
      <span><i style={{ background: "var(--hl-const)" }} />Fixed company value</span>
    </div>
  );
}
