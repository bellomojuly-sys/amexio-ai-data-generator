import type { ISODate } from "../model/dates";
import { parts } from "../model/dates";

/**
 * Output formats, exactly as they appear in AMEXIO's example package.
 *
 *  - PDFs write dates as DD-MM-YYYY            (14-04-2026)
 *  - import.xml writes dates as YYYYMMDD       (20260414)
 *  - contract documents write money with "."   (EUR 4.350)
 *  - payroll documents write money without it  (EUR 4350)
 *
 * The generator stores each fact once (ISO date, whole euros) and formats it
 * here, per output, so the two formats can never disagree.
 */

const MONTHS_EN = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
const MONTHS_NL = [
  "januari", "februari", "maart", "april", "mei", "juni",
  "juli", "augustus", "september", "oktober", "november", "december",
];

/** 2026-04-14 -> "14-04-2026" (PDF text) */
export function pdfDate(date: ISODate): string {
  const { y, m, d } = parts(date);
  return `${String(d).padStart(2, "0")}-${String(m).padStart(2, "0")}-${y}`;
}

/** 2026-04-14 -> "20260414" (import.xml <created>, <modified>, Document Date) */
export function xmlDate(date: ISODate): string {
  return date.replaceAll("-", "");
}

/** 2026-09-25 -> "September 2026" */
export function monthYear(date: ISODate): string {
  const { y, m } = parts(date);
  return `${MONTHS_EN[m - 1]} ${y}`;
}

/** 2026-09-25 -> "september 2026" (Dutch titles, lower-case month as in AMEXIO's example) */
export function monthYearNl(date: ISODate): string {
  const { y, m } = parts(date);
  return `${MONTHS_NL[m - 1]} ${y}`;
}

/** 4350 -> "EUR 4.350" (contracts, amendments) */
export function eurGrouped(amount: number): string {
  const s = String(Math.round(Math.abs(amount)));
  const grouped = s.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `EUR ${amount < 0 ? "-" : ""}${grouped}`;
}

/** 4350 -> "EUR 4350" (payslips, annual statements) */
export function eurPlain(amount: number): string {
  return `EUR ${Math.round(amount)}`;
}

/** 2 -> "2 days", 1 -> "1 day" */
export function days(n: number): string {
  return `${n} ${n === 1 ? "day" : "days"}`;
}
