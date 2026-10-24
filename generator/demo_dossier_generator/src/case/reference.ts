import { examplePreset } from "../generate/examplePreset";
import { withDefaults } from "./caseJson";
import type { RunSettings } from "./fromCase";
import type { Case } from "./generated/case";
import golden from "./generated/reference100101.json";

/**
 * The reference case 100101 (Jan de Vries), bundled from
 * case_model/reference_dossier.golden.json by `npm run types`. It is AMEXIO's
 * employee 100101 after case_model/ingest.py, so rendering it is BR-14: the
 * result must equal AMEXIO's five PDFs and import.xml entries for 100101.
 */
export function referenceCase(): Case {
  return withDefaults(JSON.parse(JSON.stringify(golden)) as Case);
}

/** AMEXIO's example run settings (period, document types, import options) for 100101. */
export function referenceRun(): RunSettings {
  const ex = examplePreset();
  return {
    config: ex.config,
    generationId: "AMEXIO-REFERENCE-100101",
    overrides: ex.overrides.filter((o) => o.employeeId === "100101"),
    updates: ex.updates,
    provenance: {
      personas: "Reference case 100101 (case_model/reference_dossier.golden.json)",
      storylines: "Reference case 100101 (case_model/reference_dossier.golden.json)",
    },
  };
}
