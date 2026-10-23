import type { DocTypeId, DocTypeSpec } from "../types";
import { employmentContract } from "./employmentContract";
import { payslip } from "./payslip";
import { medicalCheck } from "./medicalCheck";
import { performanceAppraisal } from "./performanceAppraisal";
import { trainingCertificate } from "./trainingCertificate";
import { contractAmendment } from "./contractAmendment";
import { annualIncomeStatement } from "./annualIncomeStatement";
import { absenceReport } from "./absenceReport";
import { terminationLetter } from "./terminationLetter";

/**
 * All document types, in the order their nodes appear per employee in import.xml.
 * The first five follow AMEXIO's example order (contract, payslip, medical
 * check, appraisal, training certificate). To add a type: create a module next
 * to these and add it here.
 */
export const DOC_TYPES: readonly DocTypeSpec[] = [
  employmentContract,
  payslip,
  medicalCheck,
  performanceAppraisal,
  trainingCertificate,
  contractAmendment,
  annualIncomeStatement,
  absenceReport,
  terminationLetter,
];

export const AMEXIO_DOC_TYPES: readonly DocTypeId[] = DOC_TYPES.filter((d) => d.origin === "amexio").map((d) => d.id);

const byId = new Map(DOC_TYPES.map((d) => [d.id, d]));

export function docType(id: DocTypeId): DocTypeSpec {
  const spec = byId.get(id);
  if (!spec) throw new Error(`Unknown document type: ${id}`);
  return spec;
}

export function docTypeOrder(id: DocTypeId): number {
  return DOC_TYPES.findIndex((d) => d.id === id);
}
