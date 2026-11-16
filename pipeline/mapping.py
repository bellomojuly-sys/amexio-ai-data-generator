"""Map Daniel's analysis to the case model's ingest input (BE-07).

Under Option A (team, 5 Nov) Daniel conforms to our shape, so an ``Analysis``
already has the ``employees.json`` shape that ``ingest_employees`` reads. The
mapping therefore validates the raw analysis — refusing an unknown field or an
``id`` (AX-012) — and projects it to the aliased dict the case model expects.
When Daniel's shape ever diverges from ours, the translation goes here, and only
here; the rest of the CM ID stage does not change.
"""

from __future__ import annotations

from .contracts import Analysis


def map_analysis(raw: dict) -> dict:
    """Validate Daniel's analysis and return the dict ``ingest_employees`` takes.

    Raises ``pydantic.ValidationError`` if the analysis carries an unknown field,
    an ``id``, a non-ISO date or a value outside the shape.
    """
    analysis = Analysis.model_validate(raw)
    return analysis.model_dump(by_alias=True)
