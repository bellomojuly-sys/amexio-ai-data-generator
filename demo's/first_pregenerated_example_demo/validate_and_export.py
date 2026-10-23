"""Deterministic validation and XML export for one generated dossier (demo).

Usage:
    python validate_and_export.py dossier_generated     -> finds the planted error, export blocked
    python validate_and_export.py dossier_fixed         -> all checks pass, writes export/

No AI is used here on purpose: dates, IDs, names and amounts are checked
with plain code, and the XML is written by code from the dossier model.
The XML follows the shape of OpenText Content Server's Object Importer
(<import><node type=... action="create">). Category and attribute names
are placeholders until AMEXIO shares its import schema.
"""
import json
import shutil
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

WATERMARK = "AI-GENERATED FAKE DATA"


def long_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B')} {d.year}"


def load(folder):
    folder = Path(folder)
    config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
    cast = json.loads((folder / "cast.json").read_text(encoding="utf-8"))
    events = json.loads((folder / "storyline.json").read_text(encoding="utf-8"))["events"]
    meta = json.loads((folder / "documents" / "metadata.json").read_text(encoding="utf-8"))["documents"]
    texts = {m["DocumentID"]: (folder / "documents" / m["File"]).read_text(encoding="utf-8") for m in meta}
    return config, cast, events, meta, texts


def run_checks(config, cast, events, meta, texts):
    checks = []
    add = lambda cid, title, ok, detail: checks.append(
        {"id": cid, "title": title, "status": "pass" if ok else "fail", "detail": detail})

    # 1. Required metadata
    required = config["metadata_fields"]["required"]
    missing = [f"{m['DocumentID']}: {f}" for m in meta for f in required if not m.get(f)]
    add("required", "Required metadata present", not missing,
        f"All {len(meta)} documents have the {len(required)} required fields." if not missing
        else "Missing: " + ", ".join(missing))

    # 2. References resolve
    personas, orgs = cast["personas"], cast["orgs"]
    event_ids = {e["id"] for e in events}
    doc_ids = {m["DocumentID"] for m in meta}
    refs, broken = 0, []
    for e in events:
        for p in e["participants"]:
            refs += 1
            if p not in personas: broken.append(f"{e['id']} -> {p}")
        for d in e["documents"]:
            refs += 1
            if d not in doc_ids: broken.append(f"{e['id']} -> {d}")
    for m in meta:
        refs += 1
        if m["RelatedEvent"] not in event_ids: broken.append(f"{m['DocumentID']} -> {m['RelatedEvent']}")
        for p in m["Participants"]:
            refs += 1
            if p not in personas: broken.append(f"{m['DocumentID']} -> {p}")
    for pid, p in personas.items():
        if p.get("org"):
            refs += 1
            if p["org"] not in orgs: broken.append(f"{pid} -> {p['org']}")
    add("references", "IDs and references resolve", not broken,
        f"{refs} references between personas, events and documents all point to something that exists."
        if not broken else "Broken: " + ", ".join(broken))

    # 3. Names in text match persona records
    bad = [f"{m['DocumentID']} lacks {personas[p]['name']}" for m in meta for p in m["Participants"]
           if personas[p]["name"] not in texts[m["DocumentID"]]]
    add("names", "Names match the persona records", not bad,
        "Every participant is named exactly as in personas, in every document." if not bad
        else "; ".join(bad))

    # 4. Timeline
    problems = []
    incident = next(e for e in events if e["type"] == "incident")
    prev = None
    for e in events:
        if e["id"] != incident["id"] and e["date"] < incident["date"]:
            using = [m["DocumentID"] for m in meta if long_date(e["date"]) in texts[m["DocumentID"]]]
            docs = ", ".join(using) or "no document"
            problems.append(f"{e['id']} '{e['label']}' is dated {long_date(e['date'])}, before the incident "
                            f"{incident['id']} on {long_date(incident['date'])}. Documents using this date: {docs}.")
        elif prev and e["date"] < prev["date"]:
            problems.append(f"{e['id']} ({e['date']}) comes before {prev['id']} ({prev['date']}).")
        prev = e
    add("timeline", "Timeline is in a logical order", not problems,
        f"{len(events)} events run in order from {long_date(events[0]['date'])} to {long_date(events[-1]['date'])}."
        if not problems else " ".join(problems))

    # 5. Metadata matches the document text
    mism = [f"{m['DocumentID']}: {long_date(m['DocumentDate'])} not in text" for m in meta
            if long_date(m["DocumentDate"]) not in texts[m["DocumentID"]]]
    add("meta_text", "Metadata matches the document text", not mism,
        "Each document's date in the metadata also appears in its text." if not mism else "; ".join(mism))

    # 6. Amounts add up
    est, dec = cast["estimate"], cast["decision"]
    r = lambda x: round(x + 1e-9, 2)
    amount_errors = []
    if r(est["labour_hours"] * est["labour_rate"]) != r(est["labour"]): amount_errors.append("labour")
    if r(est["parts"] + est["labour"] + est["paint"]) != r(est["subtotal"]): amount_errors.append("subtotal")
    if r(est["subtotal"] * est["vat_rate"]) != r(est["vat"]): amount_errors.append("VAT")
    if r(est["subtotal"] + est["vat"]) != r(est["total"]): amount_errors.append("total")
    if r(dec["amount"]) != r(est["total"]): amount_errors.append("decision amount")
    add("amounts", "Amounts add up", not amount_errors,
        f"Repair estimate lines add up to €{est['total']:,.2f}; the decision letter pays the same amount."
        if not amount_errors else "Wrong: " + ", ".join(amount_errors))

    # 7. Synthetic marking
    unmarked = [m["DocumentID"] for m in meta
                if WATERMARK not in texts[m["DocumentID"]] or m.get("DataType") != "SYNTHETIC"]
    add("synthetic", "Marked as synthetic data", not unmarked,
        "Every document carries the watermark and DataType = SYNTHETIC." if not unmarked
        else "Unmarked: " + ", ".join(unmarked))

    checks.append({"id": "ai_review", "title": "AI plausibility review", "status": "skip",
                   "detail": "Planned: an AI pass for things rules cannot check, such as whether the story makes sense."})
    return checks


def build_xml(config, cast, events, meta):
    claim, p = cast["claim"], cast["personas"]
    claimant = p[cast["policy"]["holder"]]["name"]
    folder_title = f"{claim['number']} {claimant}"
    incident = next(e for e in events if e["type"] == "incident")

    def attr(name, value):
        return f'      <attribute name="{escape(name)}">{escape(str(value))}</attribute>'

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           f"<!-- {WATERMARK} (SYNTHETIC) - generation {config['generation_id']} -->",
           "<!-- Shape follows the Content Server Object Importer. Category and attribute names are placeholders. -->",
           "<import>",
           '  <node type="folder" action="create">',
           "    <location>Enterprise:Claims</location>",
           f"    <title>{escape(folder_title)}</title>",
           '    <category name="Content Server Categories:Insurance Claim">',
           attr("Claim Number", claim["number"]),
           attr("Policy Number", cast["policy"]["number"]),
           attr("Claimant", claimant),
           attr("Incident Date", incident["date"]),
           attr("Status", claim["status"]),
           attr("Data Type", "SYNTHETIC"),
           "    </category>",
           "  </node>"]
    for m in meta:
        out += ['  <node type="document" action="create">',
                f"    <location>Enterprise:Claims:{escape(folder_title)}</location>",
                f"    <title>{escape(m['DocumentID'] + ' ' + m['DocumentTypeLabel'])}</title>",
                f"    <file>{escape(claim['number'] + '/' + m['File'])}</file>",
                '    <category name="Content Server Categories:Claim Document">',
                attr("Document Type", m["DocumentType"]),
                attr("Document Date", m["DocumentDate"]),
                attr("Claim Number", m["ClaimNumber"]),
                attr("Policy Number", m["PolicyNumber"]),
                attr("Claimant", m["Claimant"])]
        for opt in ("Handler", "Amount"):
            if m.get(opt):
                out.append(attr(opt, m[opt]))
        out += [attr("Related Event", m["RelatedEvent"]),
                attr("Data Type", m["DataType"]),
                "    </category>",
                "  </node>"]
    out.append("</import>")
    return "\n".join(out) + "\n"


def main(folder):
    folder = Path(folder)
    config, cast, events, meta, texts = load(folder)
    checks = run_checks(config, cast, events, meta, texts)
    errors = [c for c in checks if c["status"] == "fail"]

    icon = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}
    lines = [f"Validation report - {config['generation_id']} - {folder.name}", ""]
    for c in checks:
        lines.append(f"[{icon[c['status']]}] {c['title']}")
        lines.append(f"       {c['detail']}")
    lines.append("")
    lines.append(f"{len(errors)} error(s). " + ("Export blocked until fixed." if errors else "Export allowed."))
    report = "\n".join(lines) + "\n"
    (folder / "validation_report.txt").write_text(report, encoding="utf-8")
    print(report)
    if errors:
        return 1

    claim_no = cast["claim"]["number"]
    export = folder / "export"
    if export.exists():
        shutil.rmtree(export)
    (export / claim_no).mkdir(parents=True)
    for m in meta:
        shutil.copy(folder / "documents" / m["File"], export / claim_no / m["File"])
    (export / "import.xml").write_text(build_xml(config, cast, events, meta), encoding="utf-8")
    print(f"Export written to {export}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # euro signs on older Windows consoles
    except Exception:
        pass
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "dossier_fixed"))
