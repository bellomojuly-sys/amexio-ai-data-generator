import { PDFDocument, rgb, StandardFonts, type PDFFont, type PDFPage } from "pdf-lib";
import type { ISODate } from "../model/dates";
import { parts } from "../model/dates";
import type { RenderedDocument } from "../spec/types";
import { toWinAnsi } from "./winansi";

/**
 * Draws one document as a PDF with the layout of AMEXIO's example files
 * (measured from their content streams): A4, a red "MOCK DATA" banner across
 * the top, the title, the employee block, a rule, label/value rows with labels
 * at 2 cm and values at 8 cm, and a grey footer.
 */

const MM = 72 / 25.4;
const PAGE = { width: 595.2756, height: 841.8898 };
const LEFT = 20 * MM; // 56.69
const VALUE_X = 80 * MM; // 226.77
const RIGHT = PAGE.width - 20 * MM; // 538.58
const BANNER = { y: 779.5276, height: 62.3622, textY: 802.2047, color: rgb(0.752941, 0.223529, 0.168627) };
const TITLE_Y = 728.5039;
const IDENTITY_Y = 700.1575;
const IDENTITY_STEP = 7 * MM; // 19.84
const RULE_Y = 643.4646;
const ROWS_Y = 615.1181;
const ROW_STEP = 8 * MM; // 22.68
const LINE_HEIGHT = 14.4;
const FOOTER_Y = 20 * MM;

export interface PdfFonts {
  regular: PDFFont;
  bold: PDFFont;
  italic: PDFFont;
}

/**
 * Text width without kerning. pdf-lib's widthOfTextAtSize() applies kerning
 * pairs, but drawText() does not, so centred text would land off-centre.
 */
function plainWidth(font: PDFFont, text: string, size: number): number {
  let w = 0;
  for (const ch of text) w += font.widthOfTextAtSize(ch, size);
  return w;
}

function wrap(text: string, font: PDFFont, size: number, width: number): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let line = "";
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (plainWidth(font, candidate, size) <= width || !line) {
      line = candidate;
    } else {
      lines.push(line);
      line = word;
    }
  }
  if (line) lines.push(line);
  return lines.length ? lines : [""];
}

function drawDocument(page: PDFPage, r: RenderedDocument, fonts: PdfFonts) {
  const banner = toWinAnsi(r.banner);
  page.drawRectangle({ x: 0, y: BANNER.y, width: PAGE.width, height: BANNER.height, color: BANNER.color });
  const bw = plainWidth(fonts.bold, banner, 16);
  page.drawText(banner, { x: (PAGE.width - bw) / 2, y: BANNER.textY, size: 16, font: fonts.bold, color: rgb(1, 1, 1) });

  page.drawText(toWinAnsi(r.title), { x: LEFT, y: TITLE_Y, size: 22, font: fonts.bold, color: rgb(0, 0, 0) });

  r.identity.forEach((row, i) => {
    page.drawText(toWinAnsi(`${row.label}: ${row.value}`), {
      x: LEFT,
      y: IDENTITY_Y - i * IDENTITY_STEP,
      size: 12,
      font: fonts.regular,
      color: rgb(0, 0, 0),
    });
  });

  page.drawLine({ start: { x: LEFT, y: RULE_Y }, end: { x: RIGHT, y: RULE_Y }, thickness: 1, color: rgb(0, 0, 0) });

  let y = ROWS_Y;
  for (const row of r.rows) {
    page.drawText(toWinAnsi(`${row.label}:`), { x: LEFT, y, size: 12, font: fonts.bold, color: rgb(0, 0, 0) });
    const lines = wrap(toWinAnsi(row.value), fonts.regular, 12, RIGHT - VALUE_X);
    lines.forEach((line, i) => {
      page.drawText(line, { x: VALUE_X, y: y - i * LINE_HEIGHT, size: 12, font: fonts.regular, color: rgb(0, 0, 0) });
    });
    y -= ROW_STEP + (lines.length - 1) * LINE_HEIGHT;
  }

  page.drawText(toWinAnsi(r.footer), {
    x: LEFT,
    y: FOOTER_Y,
    size: 9,
    font: fonts.italic,
    color: rgb(0.501961, 0.501961, 0.501961),
  });
}

function asDate(date: ISODate): Date {
  const { y, m, d } = parts(date);
  return new Date(Date.UTC(y, m - 1, d, 9, 0, 0));
}

/** Renders one PDF. The PDF's own creation date is the document date, so file metadata matches import.xml. */
export async function renderPdf(r: RenderedDocument, documentDate: ISODate): Promise<Uint8Array> {
  const pdf = await PDFDocument.create();
  const fonts: PdfFonts = {
    regular: await pdf.embedFont(StandardFonts.Helvetica),
    bold: await pdf.embedFont(StandardFonts.HelveticaBold),
    italic: await pdf.embedFont(StandardFonts.HelveticaOblique),
  };
  const page = pdf.addPage([PAGE.width, PAGE.height]);
  drawDocument(page, r, fonts);
  pdf.setTitle(toWinAnsi(r.pdfTitle));
  pdf.setAuthor("anonymous");
  pdf.setCreator("anonymous");
  pdf.setSubject("unspecified");
  pdf.setProducer("AMEXIO dossier generator demo (synthetic data)");
  pdf.setKeywords(["synthetic"]);
  pdf.setCreationDate(asDate(documentDate));
  pdf.setModificationDate(asDate(documentDate));
  return pdf.save({ useObjectStreams: false });
}
