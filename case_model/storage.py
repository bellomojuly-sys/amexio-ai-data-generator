"""Save a case to files and load it back — AX-018.

A case is written as four JSON files and read back into an equal Case:

- ``case.json``       the case number and the dossier-level facts
- ``cast.json``       personas, organisations and employments
- ``storyline.json``  events
- ``documents.json``  documents

``load_case(save_case(case, d)) == case`` for any valid case.
"""

import json
from pathlib import Path

from .case_model import Case


def _write(path, payload):
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_case(case, directory):
    """Write ``case`` into ``directory`` as the four JSON files. Returns the path."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    data = case.model_dump(mode="json")

    _write(directory / "case.json", {
        "case_number": data["case_number"],
        "dossier": data["dossier"],
    })
    _write(directory / "cast.json", {
        "personas": data["personas"],
        "organisations": data["organisations"],
        "employments": data["employments"],
    })
    _write(directory / "storyline.json", {"events": data["events"]})
    _write(directory / "documents.json", {"documents": data["documents"]})
    return directory


def load_case(directory):
    """Read the four JSON files in ``directory`` back into a validated Case."""
    directory = Path(directory)
    case = _read(directory / "case.json")
    cast = _read(directory / "cast.json")
    storyline = _read(directory / "storyline.json")
    documents = _read(directory / "documents.json")

    return Case.model_validate({
        "case_number": case["case_number"],
        "dossier": case["dossier"],
        "personas": cast["personas"],
        "organisations": cast["organisations"],
        "employments": cast["employments"],
        "events": storyline["events"],
        "documents": documents["documents"],
    })
