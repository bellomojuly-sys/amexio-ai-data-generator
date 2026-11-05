"""Stage boundary contracts for the backend pipeline (BE-03).

The backend runs as one Python service; each stage is a function with a typed
input and a typed output, validated at the boundary (decision BE-01,
``docs/decisions/BE-01-backend-runtime.md``). This module names those
boundaries. It does **not** rebuild the case model: where the case model already
defines a shape, the contract reuses it.

Boundary rule (BE-01): an output that crosses between owners is exchanged as
validated JSON matching a committed JSON Schema; an output that stays in the
same process is passed as a validated pydantic object. So only the owner-to-
owner boundaries get a JSON Schema in ``pipeline/schema/``.

Stage 1 -> 2 (Daniel's analysis -> CM ID), owner to owner:
    ``Analysis``    -- what Daniel hands us. Same shape as the case model's
                       ``employees.json`` (team decision 5 Nov, Option A), so it
                       *is* the case model's ``EmployeesIn``: camelCase names, no
                       extra fields, and no ``id`` (AX-012).

Stage 2 -> 3 (CM ID -> Plot), in process:
    ``CmIdOutput``  -- the cases the CM ID stage built (IDs assigned by the case
                       model) and the corrections it recorded. ``Case`` and
                       ``Correction`` are the case model's own types.
"""

from pydantic import BaseModel

from case_model import Case
from case_model.ingest import Correction, EmployeesIn


class Analysis(EmployeesIn):
    """Stage 1 output / CM ID input: the company and its employees, as Daniel's
    first LLM call produces them.

    Option A (team, 5 Nov): Daniel conforms to our shape, so an ``Analysis`` is
    exactly an ``employees.json`` payload. Everything is inherited from
    ``EmployeesIn``: camelCase aliases, ``extra='forbid'`` (an unknown field is
    refused) and the ``_no_id`` guard (a caller- or LLM-written ``id`` is
    refused, AX-012). The CM ID stage feeds it straight to ``ingest_employees``.
    """


class CmIdOutput(BaseModel):
    """Stage 2 output / Plot input: the cases built by CM ID plus the list of
    values the case model corrected on the way in.

    This boundary stays inside our Python service (CM ID -> Plot are both
    Giulia's), so it is a pydantic object, not a JSON file. ``cases`` and
    ``corrections`` are the case model's own types -- the pipeline does not copy
    them.
    """

    cases: list[Case]
    corrections: list[Correction] = []
