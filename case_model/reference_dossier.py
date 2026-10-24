"""The HR reference dossier 100101 (Jan de Vries) — AX-016, AX-017, v1.1.

Since v1.1 (decision D1) the reference is AMEXIO's own employee 100101, not a
hand-written story. It is built the way every generated dossier is built:
AMEXIO's example, written in the generator's JSON shapes
(``fixtures/generator/amexio_example/``), goes through ``ingest`` and the
case of the first employee is the reference. So the regression test (AX-019)
also guards the ingest path that the generator uses.

The values follow the generator's AMEXIO preset (branch Demo-Generator,
``src/generate/examplePreset.ts``) and are provisional until BR-00 checks each
one against AMEXIO's PDFs and ``import.xml``. The case holds no documents yet:
document metadata comes in after that check.

All people and companies here are fictitious.
"""

import json
from pathlib import Path

from .ingest import ingest_files

FIXTURE_DIR = Path(__file__).with_name("fixtures") / "generator" / "amexio_example"


def build_reference_case():
    """Build and return the validated reference :class:`Case` 100101."""
    cases, _ = ingest_files(FIXTURE_DIR / "employees.json", FIXTURE_DIR / "storylines.json")
    return next(case for case in cases if case.case_number == "100101")


# The frozen export of the reference dossier (AX-019). The golden test in
# test_reference_dossier.py compares build_reference_case() against this file,
# so any change to a fact fails the test. Regenerate it only when the change
# is intended, with: python3 -m case_model.reference_dossier
GOLDEN_PATH = Path(__file__).with_name("reference_dossier.golden.json")


def write_golden():
    """Write the reference dossier's exported form to reference_dossier.golden.json."""
    payload = build_reference_case().model_dump(mode="json")
    GOLDEN_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return GOLDEN_PATH


if __name__ == "__main__":
    print(f"wrote {write_golden()}")
