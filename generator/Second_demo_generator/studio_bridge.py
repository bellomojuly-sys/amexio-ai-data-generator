"""Daniel's PDF Template Studio, offline mode, inside the demo page.

The studio (``pdf_template_studio/app.py``) turns example PDFs into templates
with ``{{PLACEHOLDER}}`` fields. Its offline mode needs no API: rules that know
the labels of AMEXIO's documents ("Employee:", "Gross monthly salary:", …)
find the values. This module runs **Daniel's own functions, unchanged**, in
the browser (Pyodide, with the PyMuPDF that Pyodide ships):

1. ``detect``: his ``detect_rules`` and his document-type guess (the file name,
   then his keyword signatures), with each type mapped to one of the case
   model's nine document types, as template contract v0.2 asks.
2. ``preview``: the original page, or the template made by his
   ``render_template``, as an image (his ``build_preview``).
3. ``analysis``: **demo stand-in for Daniel's step 0, Create analysis**
   (pipeline contract §3), in code only, no LLM. It reads what the detection
   found in the PDFs (employer, training provider, examiner, departments,
   positions, salaries, dates and the employees of the employment contracts)
   and proposes the run request: the run settings and the employees as seed
   employees. The user checks it and applies it to Configure.
4. ``export_templates``: the templates as a ZIP in Daniel's layout, with
   template contract v0.2's manifest.

**Why the functions are read out of app.py.** app.py builds its Streamlit
screens when it is loaded, so it cannot be imported as a library. ``studio()``
parses the file, takes the functions named in ``STUDIO_FUNCTIONS`` and the
``LABEL_KEYS`` table, and runs only those. The type signatures are read the
same way, from the ``signatures`` list in his processing step. Daniel's file
stays as it is and the demo follows every change he makes to those functions;
if he renames one, this fails loudly. (Better, later: app.py split into a
logic module and the screens.)
"""

from __future__ import annotations

import ast
import base64
import calendar
import datetime as dt
import io
import json
import re
import zipfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import get_args

from case_model.format_rules import DocumentType
from pipeline.contracts import RunRequest

ROOT = Path(__file__).resolve().parent.parent.parent
STUDIO_APP = ROOT / "pdf_template_studio" / "app.py"
STUDIO_FUNCTIONS = ("has_word_boundaries", "is_known_label_text", "document_type", "pdf_lines",
                    "detect_rules", "text_style_at", "text_width", "render_template",
                    "build_preview", "normalize_name")
DOCUMENT_TYPES = get_args(DocumentType)

# Daniel's signature labels -> the case model's document types.
SIGNATURE_TYPES = {"Payslip": "payslip", "Employment contract": "employment_contract",
                   "Medical examination": "medical_check",
                   "Training certificate": "training_certificate",
                   "Performance review": "performance_appraisal"}

# v1's positions (generator/demo_dossier_generator/src/generate/vocab.ts): the
# position list, manager flag and 40-hour salary range of known departments.
V1_POSITIONS = {
    "IT": [("Junior Software Developer", 3000, 3700, False), ("Software Developer", 3800, 4900, False),
           ("Senior Software Developer", 4800, 6000, False), ("IT Manager", 5800, 7200, True)],
    "Human Resources": [("HR Assistant", 2700, 3300, False), ("HR Advisor", 3500, 4400, False),
                        ("Senior HR Advisor", 4200, 5100, False), ("HR Manager", 5200, 6500, True)],
    "Logistics": [("Warehouse Employee", 2400, 2950, False), ("Warehouse Supervisor", 3200, 3900, False),
                  ("Logistics Planner", 3300, 4200, False), ("Logistics Manager", 4800, 6100, True)],
    "Finance": [("Accountant", 3200, 4100, False), ("Financial Controller", 4600, 5700, False),
                ("Senior Financial Controller", 5400, 6600, False), ("Finance Manager", 6000, 7400, True)],
    "Customer Service": [("Customer Service Agent", 2500, 3000, False),
                         ("Senior Customer Service Agent", 2900, 3500, False),
                         ("Team Lead Customer Service", 3400, 4200, False),
                         ("Customer Service Manager", 4500, 5600, True)],
}
DATE_FIELDS = ("START_DATE", "PAYMENT_DATE", "REVIEW_DATE", "EXAMINATION_DATE", "COMPLETED_ON")


# --- Daniel's functions, read out of app.py ---------------------------------------

@lru_cache(maxsize=1)
def studio(path: str = str(STUDIO_APP)) -> SimpleNamespace:
    """Daniel's functions and tables from app.py, run without its screens."""
    import pymupdf

    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    nodes = [node for node in tree.body
             if (isinstance(node, ast.FunctionDef) and node.name in STUDIO_FUNCTIONS)
             or (isinstance(node, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "LABEL_KEYS" for t in node.targets))]
    found = {node.name for node in nodes if isinstance(node, ast.FunctionDef)}
    if set(STUDIO_FUNCTIONS) - found or not any(isinstance(n, ast.Assign) for n in nodes):
        raise RuntimeError("pdf_template_studio/app.py no longer has "
                           f"{sorted(set(STUDIO_FUNCTIONS) - found) or ['LABEL_KEYS']}")
    namespace = {"re": re, "base64": base64, "Path": Path, "fitz": pymupdf}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), path, "exec"), namespace)
    return SimpleNamespace(signatures=_signatures(tree), fitz=pymupdf,
                           **{name: namespace[name] for name in (*STUDIO_FUNCTIONS, "LABEL_KEYS")})


def _signatures(tree: ast.Module) -> list[tuple[str, list[str]]]:
    """The keyword signatures Daniel's processing step uses to name a type."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "signatures"
                                                for t in node.targets):
            return [(label, list(clues)) for label, clues in ast.literal_eval(node.value)]
    raise RuntimeError("pdf_template_studio/app.py no longer has its type signatures")


def document_type_id(group: str) -> str | None:
    """One of the nine document types for a studio group, or None."""
    if group in SIGNATURE_TYPES:
        return SIGNATURE_TYPES[group]
    key = re.sub(r"[^a-z0-9]+", "_", group.lower()).strip("_")
    return key if key in DOCUMENT_TYPES else None


# --- 1 · Detect and organize ---------------------------------------------------------

def detect(files_json: str) -> str:
    """``files_json``: ``[{"id", "name", "path"}]`` of PDFs on Pyodide's file
    system. Per document its fields, the studio's group, the document type and
    an error, as Daniel's "Select and organize PDFs" makes them."""
    s = studio()
    out = []
    for f in json.loads(files_json):
        document = {"id": f["id"], "name": f["name"], "path": f["path"], "fields": [],
                    "error": "", "pageCount": 0, "group": s.document_type(f["name"]) or "Untitled"}
        try:
            data = Path(f["path"]).read_bytes()
            lines = s.pdf_lines(data)
            if not lines:
                raise ValueError("No selectable text found. Scanned PDFs require OCR, which is not supported.")
            with s.fitz.open(stream=data, filetype="pdf") as pdf:
                document["pageCount"] = len(pdf)
            document["fields"] = s.detect_rules(data)
            text = " ".join(lines).lower()
            for label, clues in s.signatures:
                if all(clue in text for clue in clues):
                    document["group"] = label
                    break
        except Exception as exc:          # one bad PDF never stops the batch (Daniel's rule)
            document["error"] = str(exc)
        document["documentType"] = document_type_id(document["group"])
        out.append(document)
    return json.dumps({"documents": out}, ensure_ascii=False)


# --- 2 · Preview -----------------------------------------------------------------------

def preview(path: str, fields_json: str, view: str = "template", page: int = 0) -> str:
    """One page as a PNG data URL: the original, or the template Daniel's
    ``render_template`` makes from the fields in use."""
    s = studio()
    data = Path(path).read_bytes()
    fields = json.loads(fields_json)
    warnings: list[str] = []
    if view == "template":
        data, warnings = s.render_template(data, fields)
    pages, _ = s.build_preview(data, fields, page_number=int(page))
    return json.dumps({**pages[0], "warnings": warnings})


# --- 3 · Analysis: a run request from the documents (stand-in for step 0) ---------

def _date(text: str) -> dt.date | None:
    text = text.strip()
    for pattern in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    try:                                            # "September 2026": the period of a payslip
        return dt.datetime.strptime(text, "%B %Y").date()
    except ValueError:
        return None


def _amount(text: str) -> Decimal | None:
    """ "EUR 4.350" -> 4350; "EUR 4.350,50" -> 4350.50; "EUR 4350" -> 4350."""
    digits = re.sub(r"[^\d.,]", "", text)
    if not digits:
        return None
    if "," in digits and "." in digits:
        decimal = "," if digits.rfind(",") > digits.rfind(".") else "."
    elif "," in digits:
        decimal = "," if len(digits) - digits.rfind(",") - 1 in (1, 2) else None
    elif "." in digits:
        decimal = "." if len(digits) - digits.rfind(".") - 1 in (1, 2) else None
    else:
        decimal = None
    thousands = {",", "."} - ({decimal} if decimal else set())
    for sep in thousands:
        digits = digits.replace(sep, "")
    if decimal:
        digits = digits.replace(decimal, ".")
    try:
        return Decimal(digits)
    except InvalidOperation:
        return None


def _month_end(day: dt.date) -> dt.date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def _round50(value: Decimal) -> int:
    return int(round(float(value) / 50) * 50)


def analysis(documents_json: str, request_json: str) -> str:
    """**Demo stand-in for step 0 (Daniel).** A run request proposed from the
    values the detection found, in code only. What the PDFs hold comes from
    them; what they cannot say (the shares, the notes, the director, the absence
    service, how many employees to generate) is kept from ``request_json``.
    Only the fields in use count (Daniel's "Use" column, ``replace``): a value
    the user switched off is not read. Returns the request, the facts with the
    document each came from, what was kept, and warnings."""
    documents = [d for d in json.loads(documents_json) if not d.get("error") and d.get("documentType")]
    current = json.loads(request_json)
    facts, kept, warnings = [], [], []

    def values(doc_type: str, placeholder: str):
        for d in documents:
            if d["documentType"] == doc_type:
                for field in d["fields"]:
                    if (field.get("replace", True) and field.get("placeholder") == placeholder
                            and str(field.get("original", "")).strip()):
                        yield str(field["original"]).strip(), d["name"]

    def by_employee(doc_type: str) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for d in documents:
            if d["documentType"] == doc_type:
                found = {f["placeholder"]: str(f["original"]).strip() for f in d["fields"]
                         if f.get("replace", True) and str(f.get("original", "")).strip()}
                if found.get("EMPLOYEE_ID"):
                    out.setdefault(found["EMPLOYEE_ID"], {**found, "_source": d["name"]})
        return out

    config = json.loads(json.dumps(current["config"]))
    company = config["company"]
    for key, doc_type, placeholder, label in (
        ("employerName", "employment_contract", "EMPLOYER", "Employer"),
        ("trainingProvider", "training_certificate", "PROVIDER", "Training provider"),
        ("examiner", "medical_check", "EXAMINED_BY", "Examiner"),
    ):
        seen = list(values(doc_type, placeholder))
        if seen:
            value, source = Counter(v for v, _ in seen).most_common(1)[0][0], seen[0][1]
            company[key] = value
            facts.append({"what": label, "value": value, "from": source})
        else:
            kept.append(label)
    kept += [label for key, label in (("absenceService", "Absence service"),
                                      ("directorName", "Director")) if company.get(key)]

    # Employees: one per employment contract, with the manager of their appraisal.
    contracts = by_employee("employment_contract")
    managers = by_employee("performance_appraisal")
    seeds = []
    for number in sorted(contracts):
        c = contracts[number]
        name = c.get("EMPLOYEE_NAME", "").split()
        hire = _date(c.get("START_DATE", ""))
        salary = _amount(c.get("GROSS_MONTHLY_SALARY", ""))
        hours = _amount(c.get("HOURS_PER_WEEK", ""))
        missing = [label for label, ok in (("name", len(name) >= 2), ("department", c.get("DEPARTMENT")),
                                           ("position", c.get("POSITION")), ("start date", hire),
                                           ("contract type", c.get("CONTRACT_TYPE")),
                                           ("hours", hours), ("salary", salary)) if not ok]
        if missing:
            warnings.append(f"{c['_source']}: no {', '.join(missing)} found, so employee {number} is left out")
            continue
        is_manager = any(t == c["POSITION"] and m for t, _, _, m in V1_POSITIONS.get(c["DEPARTMENT"], []))
        seed = {"firstName": name[0], "lastName": " ".join(name[1:]), "department": c["DEPARTMENT"],
                "position": c["POSITION"], "isManager": is_manager, "hireDate": hire.isoformat(),
                "contractType": c["CONTRACT_TYPE"], "hoursPerWeek": float(hours),
                "startSalary": int(salary) if salary == salary.to_integral() else float(salary)}
        manager = managers.get(number, {}).get("MANAGER")
        if manager:
            seed["managerName"] = manager
        seeds.append(seed)
        facts.append({"what": f"Seed employee {number}",
                      "value": f"{c['EMPLOYEE_NAME']}, {c['POSITION']} in {c['DEPARTMENT']}, hired "
                               f"{hire.isoformat()}, {c['CONTRACT_TYPE']}, {hours} hours, EUR {salary}"
                               + (f", manager {manager}" if manager else ""),
                      "from": c["_source"]})
    if seeds and sorted(contracts) != [str(100101 + i) for i in range(len(contracts))]:
        warnings.append("The case model numbers employees from 100101 in this order; the numbers in "
                        "the PDFs are not kept (IDs are assigned by code, AX-012).")

    # Departments and positions: those in the documents, plus v1's other
    # positions of a known department; salaries cover what the documents show.
    observed: dict[str, dict[str, list[Decimal]]] = {}
    for seed in seeds:
        observed.setdefault(seed["department"], {}).setdefault(seed["position"], []).append(
            Decimal(str(seed["startSalary"])))
    for department, _ in values("employment_contract", "DEPARTMENT"):
        observed.setdefault(department, {})
    if observed:
        departments = []
        for department, positions in observed.items():
            v1 = {title: (lo, hi, manager) for title, lo, hi, manager in V1_POSITIONS.get(department, [])}
            rows = []
            for title in dict.fromkeys([*positions, *v1]):
                seen = positions.get(title, [])
                if title in v1:
                    lo, hi, manager = v1[title]
                    lo, hi = min([lo, *map(int, seen)]), max([hi, *map(int, seen)])
                elif seen:
                    lo, hi, manager = _round50(min(seen) * Decimal("0.9")), _round50(max(seen) * Decimal("1.1")), False
                else:
                    continue
                row = {"title": title, "salaryMin": lo, "salaryMax": hi}
                if manager:
                    row["isManagerRole"] = True
                rows.append(row)
            if rows:
                departments.append({"name": department, "positions": rows})
        config["departments"] = departments
        facts.append({"what": "Departments and positions",
                      "value": "; ".join(f"{d['name']}: " + ", ".join(p["title"] for p in d["positions"])
                                         for d in departments),
                      "from": "the employment contracts, plus v1's positions of known departments"})
    else:
        kept.append("Departments and positions")

    # The as-of date: the end of the month of the latest dated document.
    dates = [(_date(v), source) for doc_type in DOCUMENT_TYPES
             for placeholder in (*DATE_FIELDS, "PERIOD") for v, source in values(doc_type, placeholder)]
    dates = [(d, source) for d, source in dates if d]
    if dates:
        latest, source = max(dates)
        config["asOfDate"] = _month_end(latest).isoformat()
        facts.append({"what": "Data as of", "value": config["asOfDate"],
                      "from": f"{source} (the end of the month of the latest document)"})
    else:
        kept.append("Data as of")

    # Seeds from the contracts replace the current seeds; the number of generated
    # employees stays. Without contracts, the seeds and the number stay as they are.
    generated = max(0, current["config"]["employeeCount"] - len(current.get("seedEmployees") or []))
    if seeds:
        config["employeeCount"] = len(seeds) + generated
    kept += ["Share on a temporary contract", "Share working part time", "Scenario notes",
             f"Number of generated employees ({generated})" if seeds else "Seed employees and number of employees"]
    temporary = sum(s["contractType"].lower() == "temporary" for s in seeds)
    part_time = sum(s["hoursPerWeek"] < 40 for s in seeds)
    if seeds:
        facts.append({"what": "In the documents", "value": f"{temporary} of {len(seeds)} on a temporary "
                      f"contract, {part_time} of {len(seeds)} part time (the shares stay as configured)",
                      "from": "the employment contracts"})

    proposed = {"config": config, "seedEmployees": seeds or current.get("seedEmployees"),
                "options": current.get("options", {})}
    try:
        RunRequest.model_validate(proposed)
    except ValueError as exc:
        return json.dumps({"error": f"The proposed run request is not valid: {exc}", "facts": facts,
                           "warnings": warnings}, ensure_ascii=False)
    return json.dumps({"request": proposed, "facts": facts, "kept": kept, "warnings": warnings,
                       "seedCount": len(seeds)}, ensure_ascii=False, default=str)


# --- 4 · Export the templates ------------------------------------------------------------

def export_templates(documents_json: str) -> bytes:
    """The templates as a ZIP in Daniel's layout (``<type>/<nnnn>_<name>_template.pdf``
    and ``_fields.json``), with template contract v0.2's ``manifest.json``."""
    s = studio()
    manifest = {"contract": "template/0.2", "domain": "HR", "documents": []}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as package:
        for index, document in enumerate(json.loads(documents_json), 1):
            if document.get("error"):
                continue
            stem = re.sub(r"[^\w.-]", "_", Path(document["name"]).stem) or "document"
            group = re.sub(r"[^\w.-]", "_", document.get("documentType") or document["group"]) or "type"
            prefix = f"{group}/{index:04d}_{stem}"
            output, warnings = s.render_template(Path(document["path"]).read_bytes(), document["fields"])
            if not document.get("documentType"):
                warnings = [*warnings, "Not one of the nine document types: the backend refuses it "
                                       "(template contract v0.2, section 3)."]
            package.writestr(prefix + "_template.pdf", output)
            package.writestr(prefix + "_fields.json", json.dumps(document["fields"], indent=2))
            manifest["documents"].append({"source": document["name"],
                                          "documentType": document.get("documentType"),
                                          "template": prefix + "_template.pdf",
                                          "fields": prefix + "_fields.json", "warnings": warnings})
        package.writestr("manifest.json", json.dumps(manifest, indent=2))
    return buffer.getvalue()
