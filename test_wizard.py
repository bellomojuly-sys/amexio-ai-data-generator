"""Wizard and PDF regression checks. Run with Python; no API calls required."""
import io
import json
import zipfile
from pathlib import Path

import pymupdf as fitz
from streamlit.testing.v1 import AppTest


def example(name="Alice Example", offset=0):
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((40 + offset, 60 + offset), f"Employee: {name}")
        page.insert_text((40 + offset, 90 + offset), "Department: Engineering")
        return pdf.tobytes()


def click(app, label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception, app.exception


def run():
    app = AppTest.from_file(str(Path(__file__).with_name("app.py"))).run()
    assert not app.exception, app.exception
    source = example()
    app.session_state["batch"]["pending"] = {
        "first": {"name": "001_contract.pdf", "bytes": source},
        "second": {"name": "002_contract.pdf", "bytes": example("Bob Example", offset=20)},
    }
    app.run()
    assert not any(button.label == "Delete" for button in app.button)
    batch = app.session_state["batch"]
    assert not batch["documents"]
    click(app, "Select and organize PDFs")
    assert batch["stage"] == 1
    assert all(d["processed"] and not d["error"] for d in batch["documents"].values())
    assert batch["documents"]["first"]["fields"][0]["original"] == "Alice Example"
    click(app, "Save & Continue")
    assert batch["stage"] == 3
    assert len(app.selectbox) == 0
    assert len(app.dataframe) == 1
    assert app.dataframe[0].proto.editing_mode == 1
    assert not any("Place a new field" in checkbox.label for checkbox in app.checkbox)
    assert not any(button.label == "Add positioned field" for button in app.button)
    bulk_label = "Reviewed and complete for all documents of this type"
    assert next(c for c in app.checkbox if c.label == bulk_label).disabled
    next(c for c in app.checkbox if c.label == "Reviewed and complete").check().run()
    assert not next(c for c in app.checkbox if c.label == bulk_label).disabled
    next(c for c in app.checkbox if c.label == bulk_label).check().run()
    assert all(d["reviewed"] for d in batch["documents"].values())
    assert any("✓ 2/2 reviewed" in b.label for b in app.button)
    next(c for c in app.checkbox if c.label == bulk_label).uncheck().run()
    assert batch["documents"]["first"]["reviewed"]
    assert not batch["documents"]["second"]["reviewed"]
    next(c for c in app.checkbox if c.label == "Reviewed and complete").uncheck().run()
    document = batch["documents"]["first"]
    document["fields"][0]["placeholder"] = "PERSON_NAME"
    document["fields"].append({"kind": "position", "replace": True, "original": "",
                                "placeholder": "SIGNATURE", "page": 0,
                                "rect": [40, 150, 240, 170], "fontsize": 10})
    document.pop("rendered", None)
    document["revision"] += 1
    document["preview_reset_nonce"] += 1
    app.run()
    assert not app.exception, app.exception
    output = document["rendered"][0]
    with fitz.open(stream=output, filetype="pdf") as pdf:
        text = pdf[0].get_text()
        assert "Alice Example" not in text
        assert "{{PERSON_NAME}}" in text
        assert "{{SIGNATURE}}" in text
        assert "Employee:" in text
    click(app, "Apply setup to other documents of this type")
    peer = batch["documents"]["second"]
    assert peer["fields"][0]["original"] == "Bob Example"
    assert peer["fields"][0]["placeholder"] == "PERSON_NAME"
    assert sum(f.get("kind") == "position" for f in peer["fields"]) == 1
    assert not peer["reviewed"]
    assert not document["reviewed"]
    next(c for c in app.checkbox if c.label == "Reviewed and complete").check().run()
    click(app, "Apply setup to other documents of this type")
    assert peer["reviewed"]
    assert document["reviewed"]
    assert any("✓ 2/2 reviewed" in button.label for button in app.button)
    click(app, "Apply setup to other documents of this type")
    assert sum(f.get("kind") == "position" for f in peer["fields"]) == 1
    # Switch away and back without losing fields.
    app.button(key="open_document_second").click().run()
    assert batch["active"] == "second"
    with fitz.open(stream=peer["rendered"][0], filetype="pdf") as pdf:
        assert "Bob Example" not in pdf[0].get_text()
        assert "{{PERSON_NAME}}" in pdf[0].get_text()
        assert "{{SIGNATURE}}" in pdf[0].get_text()
    use_key = f"use_fields_second_{peer['preview_reset_nonce']}"
    app.session_state[use_key] = {"edited_rows": {0: {"replace": False}}, "added_rows": [], "deleted_rows": []}
    app.run()
    assert not peer["fields"][0]["replace"]
    assert not peer["reviewed"]
    assert not next(checkbox for checkbox in app.checkbox if checkbox.label == "Reviewed and complete").value
    assert not any("✓ 2/2 reviewed" in button.label for button in app.button)
    with fitz.open(stream=peer["rendered"][0], filetype="pdf") as pdf:
        assert "Bob Example" in pdf[0].get_text()
    click(app, "← Previous document")
    assert batch["active"] == "first"
    click(app, "Next document →")
    assert batch["active"] == "second"
    assert not peer["fields"][0]["replace"]
    app.button(key="open_document_first").click().run()
    assert document["fields"][0]["placeholder"] == "PERSON_NAME"
    assert len(document["fields"]) == 3
    # A pending table edit and sync can arrive together in the same UI event.
    # The edit must be committed without rerunning away the button click.
    source_use_key = f"use_fields_first_{document['preview_reset_nonce']}"
    app.session_state[source_use_key] = {"edited_rows": {0: {"replace": False}}, "added_rows": [], "deleted_rows": []}
    click(app, "Apply setup to other documents of this type")
    assert not document["fields"][0]["replace"]
    assert not peer["fields"][0]["replace"]
    assert not document["reviewed"] and not peer["reviewed"]
    app.session_state[source_use_key] = {"edited_rows": {0: {"replace": True}}, "added_rows": [], "deleted_rows": []}
    click(app, "Apply setup to other documents of this type")
    assert document["fields"][0]["replace"] and peer["fields"][0]["replace"]
    assert not document["reviewed"] and not peer["reviewed"]
    # Preview edits must sync too, including an edit arriving with the button click.
    preview_key = f"preview_first_0_Template_{document['preview_reset_nonce']}"
    app.session_state[preview_key] = {"PERSON_NAME": "Chosen preview name"}
    click(app, "Apply setup to other documents of this type")
    assert document["preview_values"]["PERSON_NAME"] == "Chosen preview name"
    assert peer["preview_values"]["PERSON_NAME"] == "Chosen preview name"
    assert not document["reviewed"] and not peer["reviewed"]
    # Syncing an untouched source must not wipe another document's selections.
    peer["preview_values"] = {}
    peer["preview_reset_nonce"] += 1
    app.button(key="open_document_second").click().run()
    click(app, "Apply setup to other documents of this type")
    assert document["preview_values"]["PERSON_NAME"] == "Chosen preview name"
    # Keep as template is an explicit reset and should be transferred.
    peer_preview_key = f"preview_second_0_Template_{peer['preview_reset_nonce']}"
    app.session_state[peer_preview_key] = {"PERSON_NAME": ""}
    click(app, "Apply setup to other documents of this type")
    assert document["preview_values"]["PERSON_NAME"] == ""
    assert not document["reviewed"] and not peer["reviewed"]
    click(app, "Save & Continue")
    assert batch["stage"] == 4
    assert not batch.get("scroll_to_top", False)
    assert next(b for b in app.button if b.label == "Finish").disabled
    for d in batch["documents"].values():
        d["reviewed"] = True
    app.run()
    click(app, "Finish")
    assert batch["finished"]
    with zipfile.ZipFile(io.BytesIO(batch["archive"])) as archive:
        assert len(archive.namelist()) == 5
        manifest = json.loads(archive.read("manifest.json"))
        assert len(manifest) == 2
        assert len(set(archive.namelist())) == 5
    click(app, "Back")
    assert not batch["finished"] and batch["stage"] == 3
    assert document["fields"][0]["placeholder"] == "PERSON_NAME"
    # One unreadable PDF must not prevent the rest of the batch processing.
    click(app, "Back")
    batch["pending"]["broken"] = {"name": "broken.pdf", "bytes": b"not a PDF"}
    app.run()
    click(app, "Select and organize PDFs")
    assert batch["documents"]["broken"]["error"]
    assert not batch["documents"]["first"]["error"]
    click(app, "Save & Continue")
    assert batch["stage"] == 1
    print("PASS: stage transitions, detection, PDF redaction, positioned fields, persistence, review gate, ZIP, invalid PDFs")


if __name__ == "__main__":
    run()


