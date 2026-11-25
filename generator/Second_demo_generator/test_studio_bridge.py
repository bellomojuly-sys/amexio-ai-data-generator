"""Daniel's PDF Template Studio, offline, in the demo (``studio_bridge.py``):
his functions read out of app.py and run unchanged; detection and document
types; the template preview; the analysis that proposes the run request (demo
stand-in for step 0); and the template export.

Needs PyMuPDF (``pdf_template_studio/requirements.txt``); without it these
tests are skipped. The example PDFs are made here, in the layout of AMEXIO's
mock PDFs; the last test uses AMEXIO's own package when it is on disk (it is
not in git)."""

import ast
import io
import json
import zipfile
from pathlib import Path

import pytest

fitz = pytest.importorskip("pymupdf")

import demo_bridge  # noqa: E402
import studio_bridge as sb  # noqa: E402
from pipeline.contracts import RunRequest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
MOCK = ROOT / "generator" / "generated_mock_data" / "mock_import_dossier" / "files"


def pdf(path, *lines):
    """A one-page PDF with the lines, as AMEXIO's mock PDFs set them out."""
    with fitz.open() as doc:
        page = doc.new_page()
        for i, line in enumerate(lines):
            page.insert_text((50, 60 + 18 * i), line, fontsize=10)
        path.write_bytes(doc.tobytes())
    return path


@pytest.fixture
def documents(tmp_path):
    files = [
        pdf(tmp_path / "200101_employment_contract.pdf", "Employment Contract",
            "Employee: Eva Smit", "Employee ID: 200101", "Department: IT", "Employer:",
            "Delta Freight B.V. (fictional)", "Position:", "Software Developer", "Start date:",
            "15-04-2022", "Contract type:", "Temporary", "Hours per week:", "32",
            "Gross monthly salary:", "EUR 4.100"),
        pdf(tmp_path / "200101_performance_appraisal.pdf", "Performance Appraisal",
            "Employee: Eva Smit", "Employee ID: 200101", "Department: IT",
            "Review period: 01-01-2026 to 30-06-2026", "Manager: K. Bos (fictional)",
            "Overall rating: Meets expectations", "Review date: 30-06-2026"),
        pdf(tmp_path / "200101_training_certificate.pdf", "Training Certificate",
            "Employee: Eva Smit", "Employee ID: 200101", "Department: IT",
            "Course: Cloud Architecture Basics", "Completed on: 12-08-2026",
            "Provider: Learning Lab (fictional)", "Duration: 2 days"),
        pdf(tmp_path / "scan.pdf"),                                 # no text at all
    ]
    out = json.loads(sb.detect(json.dumps([{"id": str(i), "name": f.name, "path": str(f)}
                                           for i, f in enumerate(files)])))
    return out["documents"]


def current_request(seeds=1, count=5):
    d = json.loads(demo_bridge.defaults())
    req = d["request"]
    req["config"]["employeeCount"] = count
    req["seedEmployees"] = [d["reference"]] * seeds or None
    return req


# --- Daniel's code, unchanged -----------------------------------------------------

def test_the_studio_functions_come_from_daniels_app_py():
    s = sb.studio()
    for name in sb.STUDIO_FUNCTIONS:
        assert getattr(s, name).__code__.co_filename == str(sb.STUDIO_APP)
    assert s.LABEL_KEYS["gross monthly salary"] == "GROSS_MONTHLY_SALARY"


def test_the_type_signatures_are_the_ones_in_app_py():
    source = sb.STUDIO_APP.read_text(encoding="utf-8")
    assert sb.studio().signatures == sb._signatures(ast.parse(source))
    assert set(label for label, _ in sb.studio().signatures) == set(sb.SIGNATURE_TYPES)


# --- 1 · Detect and organize ------------------------------------------------------

def test_detection_finds_the_fields_and_the_document_type(documents):
    contract = documents[0]
    assert contract["group"] == "Employment contract" and contract["documentType"] == "employment_contract"
    found = {f["placeholder"]: f["original"] for f in contract["fields"]}
    assert found["EMPLOYEE_NAME"] == "Eva Smit" and found["GROSS_MONTHLY_SALARY"] == "EUR 4.100"
    assert documents[1]["documentType"] == "performance_appraisal"
    assert documents[2]["documentType"] == "training_certificate"


def test_a_pdf_without_text_is_named_and_the_batch_goes_on(documents):
    scan = documents[3]
    assert "No selectable text found" in scan["error"] and scan["fields"] == []
    assert not any(d["error"] for d in documents[:3])


@pytest.mark.parametrize("group, expected", [("Payslip", "payslip"), ("medical check", "medical_check"),
                                             ("absence report", "absence_report"), ("Untitled", None)])
def test_a_studio_group_maps_to_one_of_the_nine_document_types(group, expected):
    assert sb.document_type_id(group) == expected


# --- 2 · Preview --------------------------------------------------------------------

def test_the_template_preview_is_an_image_of_the_page_with_its_placeholders(documents):
    contract = documents[0]
    template = json.loads(sb.preview(contract["path"], json.dumps(contract["fields"]), "template", 0))
    original = json.loads(sb.preview(contract["path"], json.dumps(contract["fields"]), "original", 0))
    assert template["image"].startswith("data:image/png;base64,") and template["warnings"] == []
    assert template["image"] != original["image"]
    made, _ = sb.studio().render_template(Path(contract["path"]).read_bytes(), contract["fields"])
    with fitz.open(stream=made, filetype="pdf") as doc:
        assert "{{GROSS_MONTHLY_SALARY}}" in doc[0].get_text()


# --- 3 · Analysis (stand-in for step 0) -------------------------------------------

def test_the_analysis_proposes_the_run_from_the_documents(documents):
    out = json.loads(sb.analysis(json.dumps(documents), json.dumps(current_request())))
    request = RunRequest.model_validate(out["request"])
    company = request.config.company
    assert company.employer_name == "Delta Freight B.V. (fictional)"
    assert company.training_provider == "Learning Lab (fictional)"
    assert str(request.config.as_of_date) == "2026-08-31"          # the latest document's month
    (eva,) = request.seed_employees
    assert (eva.first_name, eva.last_name, str(eva.hire_date), eva.contract_type) == (
        "Eva", "Smit", "2022-04-15", "Temporary")
    assert (eva.hours_per_week, eva.start_salary, eva.manager_name) == (32, 4100, "K. Bos (fictional)")
    assert all(f["from"] for f in out["facts"])


def test_what_the_documents_cannot_say_is_kept_from_configure(documents):
    current = current_request(seeds=1, count=5)                    # 1 seed + 4 generated
    current["config"]["temporaryShare"] = 0.4
    out = json.loads(sb.analysis(json.dumps(documents), json.dumps(current)))
    config = out["request"]["config"]
    assert config["temporaryShare"] == 0.4 and config["employeeCount"] == 1 + 4
    assert config["company"]["directorName"] == current["config"]["company"]["directorName"]
    assert "Number of generated employees (4)" in out["kept"]


def test_without_contracts_the_seeds_and_the_number_stay(documents):
    current = current_request(seeds=1, count=7)
    out = json.loads(sb.analysis(json.dumps(documents[1:]), json.dumps(current)))
    assert out["seedCount"] == 0
    assert out["request"]["seedEmployees"] == current["seedEmployees"]
    assert out["request"]["config"]["employeeCount"] == 7
    assert out["request"]["config"]["company"]["trainingProvider"] == "Learning Lab (fictional)"


def test_a_field_switched_off_is_not_read(documents):
    for field in documents[0]["fields"]:
        if field["placeholder"] == "EMPLOYER":
            field["replace"] = False
    out = json.loads(sb.analysis(json.dumps(documents), json.dumps(current_request())))
    assert out["request"]["config"]["company"]["employerName"] == current_request()["config"]["company"]["employerName"]
    assert "Employer" in out["kept"]


def test_salary_ranges_cover_the_documents_and_use_v1s_ranges_where_known(documents):
    out = json.loads(sb.analysis(json.dumps(documents), json.dumps(current_request())))
    (it,) = out["request"]["config"]["departments"]
    positions = {p["title"]: p for p in it["positions"]}
    assert (positions["Software Developer"]["salaryMin"], positions["Software Developer"]["salaryMax"]) == (3800, 4900)
    assert positions["IT Manager"].get("isManagerRole") is True   # v1's manager position of IT


def test_an_unknown_department_gets_a_range_around_its_salary():
    contract = {"documentType": "employment_contract", "name": "x.pdf", "fields": [
        {"placeholder": p, "original": v} for p, v in (
            ("EMPLOYEE_NAME", "Ali Kaya"), ("EMPLOYEE_ID", "100101"), ("DEPARTMENT", "Legal"),
            ("POSITION", "Lawyer"), ("START_DATE", "01-02-2020"), ("CONTRACT_TYPE", "Permanent"),
            ("HOURS_PER_WEEK", "40"), ("GROSS_MONTHLY_SALARY", "EUR 5.000"))]}
    out = json.loads(sb.analysis(json.dumps([contract]), json.dumps(current_request())))
    (legal,) = out["request"]["config"]["departments"]
    assert legal["positions"] == [{"title": "Lawyer", "salaryMin": 4500, "salaryMax": 5500}]


@pytest.mark.parametrize("text, amount", [("EUR 4.350", 4350), ("EUR 4350", 4350),
                                          ("EUR 4.350,50", 4350.5), ("€ 1,234.56", 1234.56)])
def test_amounts_are_read_as_dutch_documents_write_them(text, amount):
    assert float(sb._amount(text)) == amount


@pytest.mark.skipif(not MOCK.is_dir(), reason="AMEXIO's mock package is not in git")
def test_amexios_mock_pdfs_give_the_case_models_amexio_example():
    files = sorted(MOCK.glob("*.pdf"))
    docs = json.loads(sb.detect(json.dumps([{"id": str(i), "name": f.name, "path": str(f)}
                                            for i, f in enumerate(files)])))["documents"]
    out = json.loads(sb.analysis(json.dumps(docs), json.dumps(current_request())))
    fixture = json.loads((ROOT / "case_model" / "fixtures" / "generator" / "amexio_example"
                          / "employees.json").read_text(encoding="utf-8"))
    assert out["request"]["seedEmployees"] == fixture["employees"]
    assert out["request"]["config"]["company"]["employerName"] == fixture["company"]["employerName"]


# --- 4 · Export ------------------------------------------------------------------------

def test_the_export_has_daniels_layout_and_contract_v02s_manifest(documents):
    with zipfile.ZipFile(io.BytesIO(sb.export_templates(json.dumps(documents)))) as archive:
        names = archive.namelist()
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["contract"] == "template/0.2" and manifest["domain"] == "HR"
    assert len(manifest["documents"]) == 3                        # the scan is left out
    first = manifest["documents"][0]
    assert first["documentType"] == "employment_contract"
    assert first["template"] in names and first["fields"] in names
    assert first["template"].startswith("employment_contract/0001_200101_employment_contract")
