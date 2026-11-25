"""Generate the case facts a domain declares, by its rules (v2.1, AX-021a "fact").

A "fact" field (Daniel's decision of 24 Nov) is a value per case that code
makes, by a rule the user approved: a value from a closed list, an amount or a
date between a minimum and a maximum. It is stored once in ``case.facts`` and
every document reads it from there, so it is the same everywhere.

- ``generate_fact(name, spec, rng)`` makes one value by its rule;
- ``generate_facts(domain, rng, given)`` makes every declared fact; a value in
  ``given`` (a constant from the approved configuration) wins and is checked.

Free text is never generated here: it is the LLM's to write. A required text
fact without a closed list must therefore be given. Chance uses the ``rng``
passed in (``random.Random(seed)``), so the same seed gives the same facts.
"""

from __future__ import annotations

import datetime as dt
import math
import random
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal

from pydantic import BaseModel

from .domain import DomainConfig, FieldSpec
from .format_rules import Money


class CannotGenerate(ValueError):
    """A fact has no rule code can generate from; it names the field."""


def _bounds(name, spec, low_default=None):
    low, high = spec.min, spec.max
    if spec.gt is not None:
        low = max(low, spec.gt + (1 if spec.format == "integer" else 0.01)) if low is not None \
            else spec.gt + (1 if spec.format == "integer" else 0.01)
    if low is None or high is None:
        raise CannotGenerate(f"{name}: needs both min and max to be generated (field {name})")
    return low, high


def _steps(name, low, high, step):
    """The first and last multiple of ``step`` inside [low, high], counted in
    steps. Raises CannotGenerate, naming the field, when there is none."""
    lo = int((Decimal(str(low)) / step).to_integral_value(rounding=ROUND_CEILING))
    hi = int((Decimal(str(high)) / step).to_integral_value(rounding=ROUND_FLOOR))
    if lo > hi:
        raise CannotGenerate(f"{name}: no value in steps of {step} lies between {low} and "
                             f"{high} (field {name})")
    return lo, hi


def generate_fact(name: str, spec: FieldSpec, rng: random.Random):
    """One value for the fact ``name`` by its rule."""
    if spec.values:
        return rng.choice(spec.values)
    if spec.format == "text":
        raise CannotGenerate(f"{name}: free text is written by the LLM or given, "
                             f"never generated (field {name})")
    if spec.format == "date":
        low, high = _bounds(name, spec)
        return low + dt.timedelta(days=rng.randint(0, (high - low).days))
    low, high = _bounds(name, spec)
    if spec.format == "integer":
        return rng.randint(math.ceil(low), math.floor(high))
    if spec.format == "number":
        # v2.2 — pick in hundredths inside the bounds, so rounding never
        # carries the value past min or max.
        lo, hi = _steps(name, low, high, Decimal("0.01"))
        return float(Decimal(rng.randint(lo, hi)) / 100)
    if spec.format == "money":
        # Whole euros, as AMEXIO's documents print them (v2.1).
        lo, hi = _steps(name, low, high, Decimal("1"))
        return Money(amount=Decimal(rng.randint(lo, hi)).quantize(Decimal("0.01")),
                     currency=spec.currency or "EUR")
    raise CannotGenerate(f"{name}: format {spec.format} is not generated (field {name})")


def generate_facts(domain: DomainConfig, rng: random.Random,
                   given: dict | None = None) -> BaseModel | None:
    """Every case fact of ``domain``: the given ones, the others generated.

    Returns the domain's facts object (checked against its formats and bounds),
    or None when the domain declares no facts. A given name the domain does not
    declare is refused; an optional fact without a rule stays empty.
    """
    given = dict(given or {})
    if domain.facts_class is None:
        if given:
            raise ValueError(f"Domain {domain.name} declares no case facts (field facts).")
        return None
    unknown = set(given) - set(domain.case_facts)
    if unknown:
        raise ValueError(f"Domain {domain.name} has no case facts "
                         f"{', '.join(sorted(unknown))} (field facts).")
    values = {}
    for name, spec in domain.case_facts.items():
        if name in given:
            values[name] = given[name]
            continue
        try:
            values[name] = generate_fact(name, spec, rng)
        except CannotGenerate:
            if spec.required:
                raise
    return domain.facts_class.model_validate(values)
