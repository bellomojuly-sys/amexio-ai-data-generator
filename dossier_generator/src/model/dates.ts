/**
 * Date helpers. Every date in the generator is an ISO calendar date string
 * ("2026-09-25"). Keeping dates as strings avoids time-zone surprises and makes
 * comparisons a simple string compare. Output formats (DD-MM-YYYY for PDFs,
 * YYYYMMDD for import.xml) are produced only at the edges, in spec/format.ts.
 */

export type ISODate = string;

const ISO_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

export function isISODate(value: unknown): value is ISODate {
  if (typeof value !== "string") return false;
  const m = ISO_RE.exec(value);
  if (!m) return false;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  if (mo < 1 || mo > 12 || d < 1) return false;
  return d <= daysInMonth(y, mo);
}

export function parts(date: ISODate): { y: number; m: number; d: number } {
  const m = ISO_RE.exec(date);
  if (!m) throw new Error(`Not an ISO date: ${date}`);
  return { y: Number(m[1]), m: Number(m[2]), d: Number(m[3]) };
}

export function iso(y: number, m: number, d: number): ISODate {
  return `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

export function daysInMonth(y: number, m: number): number {
  return new Date(Date.UTC(y, m, 0)).getUTCDate();
}

/** Adds whole months; the day is clamped to the end of the target month (31 Jan + 1 month = 28/29 Feb). */
export function addMonths(date: ISODate, months: number): ISODate {
  const { y, m, d } = parts(date);
  const total = y * 12 + (m - 1) + months;
  const ny = Math.floor(total / 12);
  const nm = (total % 12) + 1;
  return iso(ny, nm, Math.min(d, daysInMonth(ny, nm)));
}

export function addYears(date: ISODate, years: number): ISODate {
  return addMonths(date, years * 12);
}

export function addDays(date: ISODate, days: number): ISODate {
  const { y, m, d } = parts(date);
  const t = new Date(Date.UTC(y, m - 1, d + days));
  return iso(t.getUTCFullYear(), t.getUTCMonth() + 1, t.getUTCDate());
}

export function daysBetween(a: ISODate, b: ISODate): number {
  const pa = parts(a);
  const pb = parts(b);
  return Math.round((Date.UTC(pb.y, pb.m - 1, pb.d) - Date.UTC(pa.y, pa.m - 1, pa.d)) / 86_400_000);
}

export function minDate(a: ISODate, b: ISODate): ISODate {
  return a <= b ? a : b;
}

export function maxDate(a: ISODate, b: ISODate): ISODate {
  return a >= b ? a : b;
}

export function yearOf(date: ISODate): number {
  return parts(date).y;
}

export function monthStart(date: ISODate): ISODate {
  const { y, m } = parts(date);
  return iso(y, m, 1);
}

export function monthEnd(date: ISODate): ISODate {
  const { y, m } = parts(date);
  return iso(y, m, daysInMonth(y, m));
}

/** Monday = 1 ... Sunday = 7 */
export function weekday(date: ISODate): number {
  const { y, m, d } = parts(date);
  const wd = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  return wd === 0 ? 7 : wd;
}

/** Moves a weekend date to the following Monday. */
export function nextWorkday(date: ISODate): ISODate {
  const wd = weekday(date);
  if (wd === 6) return addDays(date, 2);
  if (wd === 7) return addDays(date, 1);
  return date;
}
