import type { ISODate } from "../model/dates";
import { addYears, iso, parts } from "../model/dates";

/**
 * Business rules found in AMEXIO's example package. Each one is a link between
 * documents that a generator must keep, and that the validator checks.
 */

/** Payslips are paid on the 25th of the month (all example payslips: 25-09-2026). */
export const PAY_DAY = 25;

/** Wage tax is a flat 37% of gross pay in the example. */
export const WAGE_TAX_PERCENT = 37;

/**
 * Wage tax in whole euros: 37% of gross, rounded half-to-even.
 *
 * The example shows 3450 -> 1276 (1276.5 rounded down) but 4350 -> 1610
 * (1609.5 rounded up). That is "round half to even", Python's default, which
 * suggests the example was made with a Python script. Integer arithmetic keeps
 * the result exact.
 */
export function wageTax(gross: number): number {
  const scaled = Math.round(gross) * WAGE_TAX_PERCENT; // in euro-hundredths
  const whole = Math.floor(scaled / 100);
  const rest = scaled - whole * 100;
  if (rest > 50) return whole + 1;
  if (rest < 50) return whole;
  return whole % 2 === 0 ? whole : whole + 1;
}

export function netSalary(gross: number): number {
  return Math.round(gross) - wageTax(gross);
}

/** Medical checks repeat every 2 years: "Next check" = examination date + 2 years. */
export const MEDICAL_INTERVAL_YEARS = 2;

export function nextMedicalCheck(examDate: ISODate): ISODate {
  return addYears(examDate, MEDICAL_INTERVAL_YEARS);
}

/**
 * Appraisals in the example cover the first half of the year (01-01 to 30-06)
 * and are held on the last day of that period. The title still says "2026" and
 * the description says "Yearly": noted as an open question for AMEXIO.
 */
export function appraisalPeriod(year: number): { from: ISODate; to: ISODate } {
  return { from: iso(year, 1, 1), to: iso(year, 6, 30) };
}

export function payDate(year: number, month: number): ISODate {
  return iso(year, month, PAY_DAY);
}

/** Annual income statements are issued on 31 January of the next year. */
export function annualStatementDate(year: number): ISODate {
  return iso(year + 1, 1, 31);
}

export function isPayDate(date: ISODate): boolean {
  return parts(date).d === PAY_DAY;
}
