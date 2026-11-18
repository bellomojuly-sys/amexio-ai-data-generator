"""The placeholder check of Parts 2 and 3 (pipeline contract v1.1 §7, rule 3).

**Owners: Robin, with Valentin** (contract §13). Generation never types out a
name, a date or an amount: every fact in a text is a placeholder
``{{<collection>.<key>.<field>}}`` (AX-021), which Fill later reads with the
case model's ``get_fact`` (AX-022). This module checks a generated text
against the case it belongs to, inside ``complete_as``, so a violation gets
the one retry with the problem named, and then the run fails (rule 5).

A text passes when

1. **every placeholder resolves** with ``get_fact`` on the case, to one fact
   that the case holds: an unknown collection, key or field fails, and so does
   a path that stops at a whole object (``{{personas.P001}}``) or reaches an
   empty field; a brace that is not part of a ``{{ … }}`` fails too;
2. **no fact is typed out** in the text around the placeholders:
   - no name of a person or organisation in the case: the whole name, or for
     a person one word of it (``Jan``, ``Vries``; particles such as *de* and
     *van* and words under three letters are skipped). A name that reads as a
     description, such as "Occupational physician (fictional)", is not a name;
   - no date: ISO or numeric dates, and month names (English and Dutch);
   - no amount: a currency sign or word (€, EUR, euro), a percentage;
   - no other number: any digit.

Which texts are checked (contract §5 fix 3, §7): a slot's ``summary``,
``comment`` and ``reason`` (Part 2) and every planned section (Part 3). A
training's ``course`` is not checked: it is the fact itself, not text about it.

What a list check cannot catch: a name the case does not hold (a colleague
the model invents) or a number written in words. The prompts forbid both.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from pydantic import BaseModel

from case_model import Case
from case_model.lookup import UnknownPath, get_fact

from .contracts import DocumentTextsIn, EventContentIn

# AX-021: spaces inside the braces are ignored. Fill can use the same pattern.
PLACEHOLDER = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")

EVENT_TEXT_FIELDS = ("summary", "comment", "reason")   # Part 2 texts (§5 fix 3)
MAX_SHOWN = 5             # problems named in one error; the retry gets them all at once

# Letters only, so a match never starts or ends inside a word.
_NOT_LETTER_BEFORE, _NOT_LETTER_AFTER = r"(?<![^\W\d_])", r"(?![^\W\d_])"
_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")
# Name particles and the like: not a name on their own.
_PARTICLES = {"de", "den", "der", "van", "het", "t", "'t", "ten", "ter", "te", "op", "in",
              "la", "le", "du", "da", "di", "del", "della", "dos", "das", "do", "el", "al",
              "ben", "bin", "von", "zu", "y", "e"}
_LEGAL_FORM = re.compile(r"\s+(?:B\.?\s?V\.?|N\.?\s?V\.?|Ltd\.?|Inc\.?|GmbH)$", re.IGNORECASE)

_MONTHS_EN = "January|February|March|April|May|June|July|August|September|October|November|December"
_MONTHS_NL = "januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december"
_DATE = re.compile(
    r"\d{4}-\d{1,2}-\d{1,2}"
    r"|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
    rf"|(?:\d{{1,2}}\s+)?{_NOT_LETTER_BEFORE}(?:(?:{_MONTHS_EN})|(?i:{_MONTHS_NL})){_NOT_LETTER_AFTER}"
    r"(?:\s+\d{4})?"
)
_MONEY = rf"[€$£%]|(?i:{_NOT_LETTER_BEFORE}(?:eur|euros?|percent){_NOT_LETTER_AFTER})"
_AMOUNT = re.compile(rf"(?:\d+(?:[.,]\d+)*\s*)?(?:{_MONEY})(?:\s*\d+(?:[.,]\d+)*)?")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# What is left of a placeholder with a brace missing or extra: "{personas.P001.name}".
_BROKEN = re.compile(r"\{+[^{}\s]*\}*|[^{}\s]*\}+")


class PlaceholderError(ValueError):
    """A generated text breaks rule 3. ``field`` is the path of the first bad
    text in the answer (``content.0.slots.2.comment``,
    ``documents.0.sections.feedback``), so the ``LLMError`` names it."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


def _core(name: str) -> str:
    """A name without its notes in brackets: "H. de Wit (fictional)" -> "H. de Wit"."""
    return " ".join(re.sub(r"\([^)]*\)", " ", name).split())


def _is_description(core: str) -> bool:
    """True for a label such as "Occupational physician": a word in small
    letters that is not a name particle."""
    return any(w[0].islower() and w.casefold() not in _PARTICLES for w in _WORD.findall(core))


def _phrase(text: str) -> re.Pattern:
    body = r"\s+".join(re.escape(part) for part in text.split())
    return re.compile(f"{_NOT_LETTER_BEFORE}{body}{_NOT_LETTER_AFTER}", re.IGNORECASE)


@dataclass
class _Name:
    placeholder: str
    phrases: list[re.Pattern]                        # whole names, any capitals
    words: list[str] = field(default_factory=list)   # one word of a person's name, as written


def _blank(text: str, start: int, end: int) -> str:
    return text[:start] + " " * (end - start) + text[end:]


def _shown(text: str) -> str:
    text = " ".join(text.split())
    return repr(text if len(text) <= 40 else text[:37] + "...")


class TextCheck:
    """Rule 3 for the texts of one case: build once per case, then ask
    ``problems(text)`` for each text."""

    def __init__(self, case: Case):
        self.case = case
        self.names: list[_Name] = []
        for p in case.personas.values():
            core = _core(p.name)
            if core and not _is_description(core):
                words = [w for w in _WORD.findall(core)
                         if len(w) >= 3 and w.casefold() not in _PARTICLES]
                self.names.append(_Name(f"{{{{personas.{p.id}.name}}}}", [_phrase(core)], words))
        for o in case.organisations.values():
            core = _core(o.name)
            if core and not _is_description(core):
                short = _LEGAL_FORM.sub("", core)
                phrases = [_phrase(core)] + ([_phrase(short)] if short and short != core else [])
                self.names.append(_Name(f"{{{{organisations.{o.id}.name}}}}", phrases))
        by_word: dict[str, list[str]] = {}
        for name in self.names:
            for word in name.words:
                by_word.setdefault(word, []).append(name.placeholder)
        self._words = [(re.compile(f"{_NOT_LETTER_BEFORE}{re.escape(w)}{_NOT_LETTER_AFTER}"), w,
                        placeholders) for w, placeholders in by_word.items()]

    def problems(self, text: str) -> list[str]:
        """Every way ``text`` breaks rule 3, each named for the model to fix."""
        found: list[str] = []
        rest = text
        for match in PLACEHOLDER.finditer(text):
            problem = self._resolve(match.group(1))
            if problem:
                found.append(problem)
            rest = _blank(rest, match.start(), match.end())
        broken = [m.group() for m in _BROKEN.finditer(rest)]
        if broken:
            found.append(f"{_shown(broken[0])} is not written as {{{{collection.key.field}}}}: "
                         "a brace is missing or left over")
            rest = _BROKEN.sub(lambda m: " " * len(m.group()), rest)
        for name in self.names:
            for pattern in name.phrases:
                for match in pattern.finditer(rest):
                    found.append(f"{_shown(match.group())} is a name typed out; "
                                 f"write {name.placeholder} instead")
                    rest = _blank(rest, match.start(), match.end())
        for pattern, word, placeholders in self._words:
            for match in pattern.finditer(rest):
                found.append(f"{_shown(word)} is a name typed out; write "
                             f"{' or '.join(placeholders)} instead")
                rest = _blank(rest, match.start(), match.end())
        for pattern, what, advice in (
            (_DATE, "a date", "leave it out, or use a date placeholder from the request"),
            (_AMOUNT, "an amount or percentage", "leave it out, or use a placeholder from the request"),
            (_NUMBER, "a number", "leave it out; no numbers, not even in words"),
        ):
            for match in pattern.finditer(rest):
                found.append(f"{_shown(match.group())} is {what} typed out; {advice}")
                rest = _blank(rest, match.start(), match.end())
        return found

    def _resolve(self, path: str) -> str | None:
        """Why ``{{path}}`` is not one fact of the case, or None when it is."""
        shown = f"{{{{{path}}}}}"
        try:
            value = get_fact(self.case, path)
        except UnknownPath as exc:
            return f"{shown} does not resolve: {exc}"
        if isinstance(value, BaseModel):
            return (f"{shown} is a whole {type(value).__name__}, not one fact: add the "
                    "field, such as .name or .date")
        if isinstance(value, (dict, list, tuple, set)):
            return f"{shown} is a list, not one fact"
        if value is None or value == "":
            return f"{shown} is empty in this case"
        return None


def text_problems(text: str, case: Case) -> list[str]:
    """Every way ``text`` breaks rule 3 on ``case`` (for Fill and the demo)."""
    return TextCheck(case).problems(text)


def _raise(found: list[tuple[str, str]]) -> None:
    if not found:
        return
    shown = [message for _, message in found[:MAX_SHOWN]]
    more = len(found) - len(shown)
    raise PlaceholderError("; ".join(shown) + (f"; and {more} more" if more else ""),
                           field=found[0][0])


def check_event_placeholders(cases: Mapping[str, Case], content: EventContentIn) -> None:
    """Part 2: every summary, comment and reason passes rule 3 on its case.
    ``cases`` maps employee numbers to the cases CM ID saved. An employee
    without a case is left to ``check_event_content``."""
    found = []
    for i, case_content in enumerate(content.content):
        case = cases.get(case_content.employee_number)
        if case is None:
            continue
        check = TextCheck(case)
        for j, slot in enumerate(case_content.slots):
            for name in EVENT_TEXT_FIELDS:
                text = getattr(slot, name)
                for problem in check.problems(text) if text else []:
                    found.append((f"content.{i}.slots.{j}.{name}",
                                  f"employee {case_content.employee_number}, slot {slot.slot}, "
                                  f"{name}: {problem}"))
    _raise(found)


def check_document_placeholders(case: Case, texts: DocumentTextsIn) -> None:
    """Part 3: every section of every document passes rule 3 on the case."""
    check = TextCheck(case)
    found = []
    for i, document in enumerate(texts.documents):
        for section, text in document.sections.items():
            for problem in check.problems(text):
                found.append((f"documents.{i}.sections.{section}",
                              f"employee {texts.employee_number}, {document.doc}, {section}: "
                              f"{problem}"))
    _raise(found)
