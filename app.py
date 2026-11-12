import hashlib
import base64
import copy
import io
import json
import os
import re
import zipfile
from pathlib import Path

import pymupdf as fitz
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

pdf_preview = components.declare_component(
    "pdf_template_preview",
    path=str(Path(__file__).parent / "pdf_preview_component"),
)

st.set_page_config(page_title="PDF Template Studio", page_icon="ðŸ“„", layout="wide")
st.title("PDF Template Studio")
st.caption("Select PDFs, organize document types, edit templates, and export your batch.")

LABEL_KEYS = {
    "employee": "EMPLOYEE_NAME", "employee id": "EMPLOYEE_ID", "department": "DEPARTMENT",
    "employer": "EMPLOYER", "position": "POSITION", "start date": "START_DATE",
    "contract type": "CONTRACT_TYPE", "hours per week": "HOURS_PER_WEEK",
    "gross monthly salary": "GROSS_MONTHLY_SALARY", "examination date": "EXAMINATION_DATE",
    "examined by": "EXAMINED_BY", "result": "RESULT", "next check": "NEXT_CHECK",
    "period": "PERIOD", "payment date": "PAYMENT_DATE",
    "course": "COURSE", "completed on": "COMPLETED_ON", "provider": "PROVIDER",
    "duration": "DURATION", "review period": "REVIEW_PERIOD", "manager": "MANAGER",
    "overall rating": "OVERALL_RATING", "review date": "REVIEW_DATE",
    "gross salary": "GROSS_SALARY", "wage tax": "WAGE_TAX", "net salary": "NET_SALARY",
}


def has_word_boundaries(text, value):
    for match in re.finditer(re.escape(value), text):
        before = text[match.start() - 1] if match.start() else ""
        after = text[match.end()] if match.end() < len(text) else ""
        if not (before.isalnum() or before == "_") and not (after.isalnum() or after == "_"):
            return True
    return False


def is_known_label_text(value):
    normalized = re.sub(r"[\W_]+", " ", str(value).strip().lower()).strip()
    if not normalized:
        return False
    labels = [re.sub(r"\s+", " ", label.lower()).strip() for label in LABEL_KEYS]
    return any(
        normalized == label
        or (
            len(normalized) >= 3
            and normalized in label
            and not has_word_boundaries(label, normalized)
        )
        for label in labels
    )


def navigate_document(step):
    document_order = st.session_state.document_order
    current_index = document_order.index(st.session_state.active_doc_hash)
    next_index = max(0, min(len(document_order) - 1, current_index + step))
    st.session_state.active_doc_hash = document_order[next_index]


def document_type(filename):
    stem = Path(filename).stem.lower()
    stem = re.sub(r"^\d+[\s_-]+", "", stem)
    return re.sub(r"[^a-z0-9]+", " ", stem).strip()


def collect_recommendations(available_documents, documents, active_hash, active_fields):
    active_type = document_type(available_documents[active_hash]["name"])
    recommendations = {}
    for document_hash, uploaded in available_documents.items():
        if document_type(uploaded["name"]) != active_type:
            continue
        fields = active_fields if document_hash == active_hash else documents[document_hash]["fields"]
        for field in fields:
            if not field.get("replace") or not str(field.get("placeholder", "")).strip():
                continue
            name = re.sub(r"[^A-Z0-9_]", "_", str(field["placeholder"]).upper()).strip("_")
            original = str(field.get("original", "")).strip()
            if name and original:
                options = recommendations.setdefault(name, [])
                if original not in options:
                    options.append(original)
    return recommendations


def pdf_lines(pdf_bytes):
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        return [line.strip() for page in doc for line in page.get_text().splitlines() if line.strip()]


def detect_rules(pdf_bytes):
    """Offline fallback: known labels from example documents, with no AI dependency."""
    result = []
    lines = pdf_lines(pdf_bytes)
    parsed = []
    for line in lines:
        if ":" not in line:
            parsed.append((None, line.strip()))
            continue
        label, value = line.split(":", 1)
        label = re.sub(r"\s+", " ", label.strip().lower())
        parsed.append((label if label in LABEL_KEYS else None, value.strip()))

    i = 0
    while i < len(parsed):
        label, value = parsed[i]
        if label is None:
            i += 1
            continue
        if value:
            if not is_known_label_text(value):
                result.append({"replace": True, "original": value, "placeholder": LABEL_KEYS[label]})
            i += 1
            continue

        group_end = i
        while group_end < len(parsed) and parsed[group_end][0] and not parsed[group_end][1]:
            group_end += 1
        group_size = group_end - i
        if group_size > 1:
            values = parsed[group_end:group_end + group_size]
            if len(values) == group_size and all(not value_label for value_label, _ in values):
                for (field_label, _), (_, field_value) in zip(parsed[i:group_end], values):
                    if field_value and not is_known_label_text(field_value):
                        result.append({
                            "replace": True,
                            "original": field_value,
                            "placeholder": LABEL_KEYS[field_label],
                        })
                i = group_end + group_size
                continue

        if i + 1 < len(parsed):
            next_label, next_value = parsed[i + 1]
            fallback_value = next_value if next_label is None else ""
            if fallback_value and not is_known_label_text(fallback_value):
                result.append({
                    "replace": True,
                    "original": fallback_value,
                    "placeholder": LABEL_KEYS[label],
                })
                i += 2
                continue
        i += 1
    return result


def detect_ai(pdf_bytes, api_key, model):
    from openai import OpenAI
    lines = pdf_lines(pdf_bytes)
    if not lines:
        return []
    prompt = "\n".join(lines[:500])
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": (
                "Identify replaceable example values in the provided PDF text. Return JSON only: "
                '{"fields":[{"original":"exact text from document","placeholder":"UPPERCASE_SNAKE_CASE"}]}. '
                "Use only exact nonempty values, never partial words or substrings of larger words. "
                "Exclude headings, labels, boilerplate, "
                "and disclaimer text. Prefer employee and document-specific values, dates, names, amounts, IDs, "
                "departments and status/results. Do not return duplicate originals."
            )},
            {"role": "user", "content": prompt},
        ],
    )
    data = json.loads(response.choices[0].message.content)
    out = []
    full_text = "\n".join(lines)
    for item in data.get("fields", []):
        original = str(item.get("original", "")).strip()
        placeholder = re.sub(r"[^A-Z0-9_]", "_", str(item.get("placeholder", "")).upper()).strip("_")
        if (
            original
            and placeholder
            and not is_known_label_text(original)
            and has_word_boundaries(full_text, original)
        ):
            out.append({"replace": True, "original": original, "placeholder": placeholder})
    return out


def text_style_at(page, rect):
    closest_span = None
    closest_overlap = 0
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                span_rect = fitz.Rect(span["bbox"])
                overlap = (span_rect & rect).get_area()
                if overlap > closest_overlap:
                    closest_span = span
                    closest_overlap = overlap

    if closest_span is None:
        return {
            "fontname": "helv",
            "fontsize": min(10.5, max(4.5, rect.height * 0.76)),
            "baseline": rect.y1 - 2,
            "color": (0, 0, 0),
        }

    fontname = "helv"
    span_font = re.sub(r"^[A-Z]{6}\+", "", closest_span["font"])
    normalized_span_font = re.sub(r"[^a-z0-9]", "", span_font.lower())
    for font in page.get_fonts(full=True):
        base_font = re.sub(r"^[A-Z]{6}\+", "", font[3])
        normalized_base_font = re.sub(r"[^a-z0-9]", "", base_font.lower())
        if normalized_base_font == normalized_span_font:
            fontname = font[4]
            break
    else:
        if "bold" in normalized_span_font and "italic" in normalized_span_font:
            fontname = "hebi"
        elif "bold" in normalized_span_font:
            fontname = "hebo"
        elif "italic" in normalized_span_font or "oblique" in normalized_span_font:
            fontname = "heit"

    color_value = closest_span["color"]
    color = (
        ((color_value >> 16) & 255) / 255,
        ((color_value >> 8) & 255) / 255,
        (color_value & 255) / 255,
    )
    return {
        "fontname": fontname,
        "fontsize": closest_span["size"],
        "baseline": closest_span["origin"][1],
        "color": color,
    }


def text_width(text, fontname, fontsize):
    try:
        return fitz.get_text_length(text, fontname=fontname, fontsize=fontsize)
    except ValueError:
        return fitz.get_text_length(text, fontname="helv", fontsize=fontsize)


def render_template(pdf_bytes, fields):
    """Redact exact matched text then overlay placeholder, checking for available space."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    warnings = []
    active = [f for f in fields if f.get("replace") and str(f.get("original", "")).strip() and str(f.get("placeholder", "")).strip()]
    # Longer originals first to avoid replacing substrings in shorter values.
    active.sort(key=lambda f: len(str(f["original"])), reverse=True)
    matched = set()
    skipped_matches = set()
    for page_no, page in enumerate(doc):
        replacements = []
        occupied = []
        words = page.get_text("words")
        for f in active:
            original = str(f["original"]).strip()
            placeholder = "{{" + re.sub(r"[^A-Z0-9_]", "_", str(f["placeholder"]).upper()).strip("_") + "}}"
            if is_known_label_text(original):
                warnings.append(f"Page {page_no+1}: label text skipped as a value: {original}")
                continue
            for rect in page.search_for(original):
                partial_word = False
                for word in words:
                    word_rect = fitz.Rect(word[:4])
                    if not rect.intersects(word_rect):
                        continue
                    margin = 0.5
                    if (
                        rect.x0 > word_rect.x0 + margin
                        or rect.y0 > word_rect.y0 + margin
                        or rect.x1 < word_rect.x1 - margin
                        or rect.y1 < word_rect.y1 - margin
                    ):
                        partial_word = True
                        break
                if partial_word:
                    skipped_matches.add(original)
                    continue
                if any(rect.intersects(prev) for prev in occupied):
                    skipped_matches.add(original)
                    continue
                occupied.append(rect)
                matched.add(original)
                style = text_style_at(page, rect)
                # Redaction removes old characters, avoiding accidental exposure.
                page.add_redact_annot(rect, fill=(1, 1, 1))
                replacements.append((rect, placeholder, original, style))
        if replacements:
            page.apply_redactions(images=0, graphics=0, text=0)
            for rect, placeholder, original, style in replacements:
                size = style["fontsize"]
                available = max(1, page.rect.width - rect.x0 - 20)
                while text_width(placeholder, style["fontname"], size) > available and size > 4.5:
                    size -= 0.25
                if text_width(placeholder, style["fontname"], size) > available:
                    warnings.append(f"Page {page_no+1}: placeholder may overflow: {placeholder}")
                # White rectangle beyond original text gives room for a longer placeholder.
                width = min(available, text_width(placeholder, style["fontname"], size) + 3)
                extra = fitz.Rect(rect.x0, rect.y0, rect.x0 + width, rect.y1)
                page.draw_rect(extra, color=None, fill=(1, 1, 1), overlay=True)
                page.insert_text((rect.x0, style["baseline"]), placeholder,
                                 fontname=style["fontname"], fontsize=size, color=style["color"], overlay=True)
    for field in active:
        original = str(field["original"]).strip()
        if original not in matched and original not in skipped_matches:
            warnings.append(f"No replaceable match found: {original}")
    for field in fields:
        if not field.get("replace") or field.get("kind") != "position":
            continue
        name = normalize_name(field.get("placeholder", ""))
        if not name:
            continue
        page = doc[int(field["page"])]
        rect = fitz.Rect(field["rect"])
        placeholder = "{{" + name + "}}"
        size = float(field.get("fontsize", 10))
        while text_width(placeholder, "helv", size) > rect.width and size > 4.5:
            size -= 0.25
        if text_width(placeholder, "helv", size) > rect.width or size + 3 > rect.height:
            warnings.append(f"Page {page.number + 1}: positioned field may overflow: {placeholder}")
        page.insert_text((rect.x0, rect.y0 + size), placeholder, fontsize=size, overlay=True)
    result = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return result, warnings


def render_filled_template(template_bytes, values):
    doc = fitz.open(stream=template_bytes, filetype="pdf")
    for page in doc:
        replacements = []
        for placeholder_name, value in values.items():
            value = str(value).strip()
            if not value:
                continue
            placeholder = "{{" + placeholder_name + "}}"
            for rect in page.search_for(placeholder):
                style = text_style_at(page, rect)
                page.add_redact_annot(rect, fill=(1, 1, 1))
                replacements.append((rect, value, style))
        if replacements:
            page.apply_redactions(images=0, graphics=0, text=0)
            for rect, value, style in replacements:
                size = style["fontsize"]
                available = max(1, page.rect.width - rect.x0 - 20)
                while text_width(value, style["fontname"], size) > available and size > 4.5:
                    size -= 0.25
                width = min(available, text_width(value, style["fontname"], size) + 3)
                page.draw_rect(fitz.Rect(rect.x0, rect.y0, rect.x0 + width, rect.y1),
                               color=None, fill=(1, 1, 1), overlay=True)
                page.insert_text((rect.x0, style["baseline"]), value,
                                 fontname=style["fontname"], fontsize=size, color=style["color"], overlay=True)
    result = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return result


def build_preview(preview_bytes, fields, target_bytes=None, page_number=0):
    doc = fitz.open(stream=preview_bytes, filetype="pdf")
    target_doc = fitz.open(stream=target_bytes, filetype="pdf") if target_bytes else doc
    pages = []
    targets = []
    placeholder_names = {
        "{{" + re.sub(r"[^A-Z0-9_]", "_", str(field.get("placeholder", "")).upper()).strip("_") + "}}"
        for field in fields
        if field.get("replace") and str(field.get("placeholder", "")).strip()
    }
    for page_no in [page_number]:
        page = doc[page_no]
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        pages.append({"image": "data:image/png;base64," + base64.b64encode(pix.tobytes("png")).decode(),
                      "width": page.rect.width, "height": page.rect.height})
    for page_no in [page_number]:
        page = target_doc[page_no]
        for placeholder in placeholder_names:
            for rect in page.search_for(placeholder):
                targets.append({
                    "page": 0,
                    "name": placeholder[2:-2],
                    "rect": [rect.x0, rect.y0, rect.x1, rect.y1],
                })
    doc.close()
    if target_doc is not doc:
        target_doc.close()
    return pages, targets


def normalize_name(value):
    return re.sub(r"[^A-Z0-9_]", "_", str(value).upper()).strip("_")


def apply_type_setup(source, target):
    """Transfer field choices by PDF location while retaining the target's values."""
    fields = copy.deepcopy(target["fields"])
    applied = skipped = 0
    with fitz.open(stream=source["bytes"], filetype="pdf") as source_pdf, \
            fitz.open(stream=target["bytes"], filetype="pdf") as target_pdf:
        candidates = [f for f in fields if f.get("kind") != "position"]
        # Offline hints can also resolve fields removed from the target's editor.
        candidates += detect_rules(target["bytes"])
        source_hints = detect_rules(source["bytes"])
        used = set()
        for field in source["fields"]:
            if field.get("kind") == "position":
                page_no = int(field["page"])
                if page_no >= len(target_pdf) or tuple(source_pdf[page_no].rect) != tuple(target_pdf[page_no].rect):
                    skipped += 1
                    continue
                fields = [f for f in fields if not (f.get("kind") == "position" and
                          f["page"] == page_no and f["rect"] == field["rect"])]
                fields.append(copy.deepcopy(field))
                applied += 1
                continue
            original = str(field.get("original", "")).strip()
            # The same field can move between PDFs (wrapping, different fonts,
            # or page sizes). Prefer its semantic name over exact coordinates.
            names = {normalize_name(field.get("placeholder", ""))}
            names.update(normalize_name(hint["placeholder"]) for hint in source_hints if hint["original"] == original)
            semantic = {str(candidate.get("original", "")).strip() for candidate in candidates
                        if normalize_name(candidate.get("placeholder", "")) in names
                        and str(candidate.get("original", "")).strip()}
            locations = [(page.number, rect) for page in source_pdf for rect in page.search_for(original)] if original else []
            matches = semantic if len(semantic) == 1 else set()
            for page_no, rect in ([] if matches else locations):
                if page_no >= len(target_pdf) or tuple(source_pdf[page_no].rect) != tuple(target_pdf[page_no].rect):
                    continue
                page = target_pdf[page_no]
                nearby = set()
                for candidate in candidates:
                    value = str(candidate.get("original", "")).strip()
                    if value and any(abs(hit.x0 - rect.x0) < 3 and abs(hit.y0 - rect.y0) < 3
                                     for hit in page.search_for(value)):
                        nearby.add(value)
                if len(nearby) == 1:
                    matches.update(nearby)
                elif not nearby:
                    # An undetected, longer value cannot safely be inferred from
                    # the source rectangle. Only reuse an exact value at this location.
                    if any(abs(hit.x0 - rect.x0) < 3 and abs(hit.y0 - rect.y0) < 3
                           for hit in page.search_for(original)):
                        matches.add(original)
            if len(matches) != 1 or next(iter(matches), None) in used:
                skipped += 1
                continue
            value = matches.pop()
            used.add(value)
            replacement = dict(field, original=value)
            existing = next((f for f in fields if f.get("kind") != "position" and f.get("original") == value), None)
            if existing is None:
                fields.append(replacement)
            else:
                existing.update(replacement)
            applied += 1
    return fields, applied, skipped


def init_batch():
    return {"stage": 1, "documents": {}, "pending": {}, "groups": [],
            "active": None, "finished": False, "upload_nonce": 0}


def paginated_items(items, key, page_size=10):
    """Bound the number of navigation controls even for very large batches."""
    count = max(1, (len(items) + page_size - 1) // page_size)
    page = min(st.session_state.get(key, 0), count - 1)
    previous, status, following = st.columns([1, 2, 1])
    if previous.button("Previous", key=f"{key}_previous", disabled=page == 0):
        st.session_state[key] = page - 1
        st.rerun()
    status.caption(f"Page {page + 1} of {count} · {len(items)} results")
    if following.button("Next", key=f"{key}_next", disabled=page >= count - 1):
        st.session_state[key] = page + 1
        st.rerun()
    return items[page * page_size:(page + 1) * page_size]


batch = st.session_state.setdefault("batch", init_batch())


def move_stage(stage):
    batch["stage"] = stage
    batch["finished"] = False
    batch["scroll_to_top"] = True
    st.rerun()


def invalidate(document):
    document["reviewed"] = False
    document["revision"] += 1
    document.pop("rendered", None)
    batch["finished"] = False


def output_for(document):
    cached = document.get("rendered")
    if cached is None:
        cached = render_template(document["bytes"], document["fields"])
        document["rendered"] = cached
    return cached


def group_status(group):
    members = [d for d in batch["documents"].values() if d["group"] == group]
    ready = sum(d["reviewed"] and not d["error"] for d in members)
    return f"{'✓ ' if members and ready == len(members) else ''}{ready}/{len(members)} reviewed"


def update_reviewed(identity, widget_key):
    batch["documents"][identity]["reviewed"] = bool(st.session_state[widget_key])
    batch["finished"] = False


def update_type_reviewed(identity, widget_key):
    source = batch["documents"][identity]
    checked = bool(st.session_state[widget_key]) and source["reviewed"]
    failed = []
    for peer_id, peer in batch["documents"].items():
        if peer_id == identity or peer["group"] != source["group"]:
            continue
        ready = checked
        if checked:
            try:
                ready = peer["processed"] and not peer["error"] and not field_errors(peer)
                if ready:
                    output_for(peer)
            except Exception:
                ready = False
            if not ready:
                failed.append(peer["name"])
        if peer["reviewed"] != bool(ready):
            peer["reviewed"] = bool(ready)
            peer["revision"] += 1
    batch["finished"] = False
    if failed:
        batch["review_notice"] = "These documents could not be marked complete: " + ", ".join(failed)


def commit_use_fields(identity, widget_key):
    """Commit pending editor changes before navigation or sync buttons run."""
    document = batch["documents"][identity]
    if widget_key not in st.session_state or "use_seed" not in document:
        return
    fields = copy.deepcopy(document["use_seed"])
    edits = st.session_state[widget_key].get("edited_rows", {})
    for row, changes in edits.items():
        index = int(row)
        if 0 <= index < len(fields) and "replace" in changes:
            fields[index]["replace"] = bool(changes["replace"])
    if fields != document["fields"]:
        document["fields"] = fields
        invalidate(document)


def commit_preview_values(identity, widget_key):
    document = batch["documents"][identity]
    event = st.session_state.get(widget_key)
    if not isinstance(event, dict) or "kind" in event:
        return
    names = {normalize_name(f["placeholder"]) for f in document["fields"] if f.get("replace")}
    values = {name: str(value) for name, value in event.items() if name in names}
    if values != document["preview_values"]:
        document["preview_values"] = values
        invalidate(document)


def field_errors(document):
    errors = []
    for index, field in enumerate(document["fields"], 1):
        if not field.get("replace"):
            continue
        if not normalize_name(field.get("placeholder", "")):
            errors.append(f"Field {index}: enter a placeholder name.")
        if field.get("kind") != "position" and not str(field.get("original", "")).strip():
            errors.append(f"Field {index}: enter exact PDF text.")
    return errors


with st.sidebar:
    st.header("Detection settings")
    mode = st.radio("Detect fields using", ["Offline example rules", "OpenAI"])
    api_key = ""
    model = "gpt-4o-mini"
    if mode == "OpenAI":
        api_key = st.text_input("OpenAI API key", value=os.getenv("OPENAI_API_KEY", ""), type="password")
        model = st.text_input("Model", value=model)
    st.caption("OpenAI mode sends extracted PDF text to the API. Upload only authorized documents.")

stages = {1: "Select & Organize", 3: "Edit Templates", 4: "Review & Export"}
if batch["stage"] == 2:
    batch["stage"] = 1
step = {1: 1, 3: 2, 4: 3}[batch["stage"]]
st.progress(step / 3, text=f"Step {step} of 3 — {stages[batch['stage']]}")
if batch.pop("scroll_to_top", False):
    components.html("""<script>
    function resetScroll() {
      try {
        const host = window.parent;
        host.scrollTo(0, 0);
        host.document.querySelectorAll('[data-testid="stMain"], .stMain, .main, main')
          .forEach(node => node.scrollTo(0, 0));
      } catch (error) { /* Host browser may restrict frame access. */ }
    }
    requestAnimationFrame(resetScroll);
    setTimeout(resetScroll, 150);
    setTimeout(resetScroll, 400);
    </script>""", height=0)

if batch["stage"] == 1:
    st.subheader("Select & Organize")
    st.caption("Keep your selection in Add PDFs, then press Select and organize PDFs to process it and show document types.")
    upload_key = f"uploads_{batch['upload_nonce']}"
    if upload_key not in st.session_state:
        # The uploader is recreated after returning from another step; retain
        # the confirmed selection rather than interpreting this as removal.
        batch["upload_signature"] = []
    uploads = st.file_uploader("Add PDFs", type=["pdf"], accept_multiple_files=True, key=upload_key)
    if uploads is not None:
        incoming = {}
        duplicate_counts = {}
        for upload in uploads:
            content = upload.getvalue()
            base = hashlib.sha256(content + upload.name.encode()).hexdigest()
            occurrence = duplicate_counts.get(base, 0)
            duplicate_counts[base] = occurrence + 1
            incoming[f"{base}:{occurrence}"] = {"name": upload.name, "bytes": content}
        signature = list(incoming)
        if signature != batch.get("upload_signature", []):
            ignored = set(batch.get("deleted_uploads", [])) & set(incoming)
            batch["deleted_uploads"] = list(ignored)
            for removed in set(batch.get("upload_signature", [])) - set(incoming):
                batch["pending"].pop(removed, None)
            batch["pending"].update({key: value for key, value in incoming.items() if key not in ignored})
            batch["upload_signature"] = signature
    pending = batch["pending"]
    process = st.button("Select and organize PDFs", type="primary", disabled=not pending)
    if process:
        documents = batch["documents"]
        for identity in list(documents):
            if identity not in pending:
                del documents[identity]
        for identity, source in pending.items():
            if identity not in documents:
                group = document_type(source["name"]) or "Untitled"
                documents[identity] = {**source, "group": group, "fields": [], "processed": False,
                                       "error": "", "reviewed": False, "revision": 0,
                                       "last_detection": "Not processed", "preview_values": {}, "preview_reset_nonce": 0}
                if group not in batch["groups"]:
                    batch["groups"].append(group)
    documents = batch["documents"]
    if process:
        if mode == "OpenAI" and not api_key:
            st.error("Enter an OpenAI API key first.")
        else:
            targets = [d for d in documents.values() if not d["processed"] or d["error"]]
            progress = st.progress(0, text="Processing documents")
            for index, document in enumerate(targets):
                try:
                    lines = pdf_lines(document["bytes"])
                    if not lines:
                        raise ValueError("No selectable text found. Scanned PDFs require OCR, which is not supported.")
                    with fitz.open(stream=document["bytes"], filetype="pdf") as pdf:
                        document["page_count"] = len(pdf)
                    document["fields"] = detect_ai(document["bytes"], api_key, model) if mode == "OpenAI" else detect_rules(document["bytes"])
                    document["last_detection"] = mode
                    # Only refine a newly suggested group; preserve manual assignments on retries.
                    if not document["processed"]:
                        text = " ".join(lines).lower()
                        signatures = [("Payslip", ["wage tax", "net salary"]),
                                      ("Employment contract", ["contract type", "hours per week"]),
                                      ("Medical examination", ["examination date", "examined by"]),
                                      ("Training certificate", ["course", "completed on"]),
                                      ("Performance review", ["review period", "overall rating"])]
                        for label, clues in signatures:
                            if all(clue in text for clue in clues):
                                document["group"] = label
                                if label not in batch["groups"]:
                                    batch["groups"].append(label)
                                break
                    document["error"] = ""
                    invalidate(document)
                except Exception as exc:
                    document["error"] = str(exc)
                document["processed"] = True
                progress.progress((index + 1) / len(targets), text=f"Processed {index + 1}/{len(targets)}")
            batch["groups"] = list(dict.fromkeys(d["group"] for d in documents.values()))
            batch["organize_revision"] = batch.get("organize_revision", 0) + 1
            st.rerun()
    if not documents:
        st.info("Select PDFs in Add PDFs, then press Select and organize PDFs to begin.")
        st.stop()
    st.subheader("Organize document types")
    with st.form("organize"):
        assignments = pd.DataFrame([{"ID": identity, "Document": d["name"], "Document type": d["group"],
                                     "Status": d["error"] or ("Ready" if d["processed"] else "Waiting for processing")}
                                    for identity, d in documents.items()])
        edited = st.data_editor(assignments, hide_index=True, disabled=["ID", "Document", "Status"],
                                column_config={"ID": None}, key=f"group_assignments_{batch.get('organize_revision', 0)}")
        st.caption("Enter an existing type to merge groups, or a new name to create or rename a type.")
        continue_groups = st.form_submit_button("Save & Continue", type="primary")
    if continue_groups:
        if set(documents) != set(pending):
            st.error("Your selection changed. Press Select and organize PDFs to update the batch first.")
        elif any(not str(value).strip() for value in edited["Document type"]):
            st.error("Every document needs a document type.")
        else:
            for row in edited.to_dict("records"):
                doc = documents[row["ID"]]
                new_group = str(row["Document type"]).strip()
                if doc["group"] != new_group:
                    doc["group"] = new_group
                    invalidate(doc)
            batch["groups"] = list(dict.fromkeys(d["group"] for d in documents.values()))
            if any(not d["processed"] or d["error"] for d in documents.values()):
                st.error("Process all documents successfully before continuing. Remove unsupported PDFs in step 1.")
            else:
                move_stage(3)

elif batch["stage"] == 3:
    documents = batch["documents"]
    active_id = batch.get("active")
    if active_id in documents:
        active_document = documents[active_id]
        commit_use_fields(active_id, f"use_fields_{active_id}_{active_document['preview_reset_nonce']}")
        if st.session_state.get(f"view_{active_id}", "Template") == "Template":
            page_no = int(st.session_state.get(f"page_{active_id}", 1)) - 1
            commit_preview_values(active_id, f"preview_{active_id}_{page_no}_Template_{active_document['preview_reset_nonce']}")
    if batch.get("apply_notice"):
        st.success(batch.pop("apply_notice"))
    with st.sidebar:
        st.header("Document types")
        query = st.text_input("Search types")
        groups = [g for g in batch["groups"] if query.casefold() in g.casefold()]
        active = batch.get("active")
        if active not in documents:
            active = next(iter(documents))
            batch["active"] = active
        for group in paginated_items(groups, f"type_page_{query}"):
            if st.button(f"{group} · {group_status(group)}", key=f"group_{group}",
                         type="primary" if documents[active]["group"] == group else "secondary"):
                batch["active"] = next(identity for identity, d in documents.items() if d["group"] == group)
                st.rerun()
        if not groups:
            st.caption("No matching document types.")
    identity = batch["active"]
    document = documents[identity]
    members = [key for key, d in documents.items() if d["group"] == document["group"]]
    st.subheader(document["group"])
    with st.expander("Browse documents in this type", expanded=True):
        document_query = st.text_input("Search documents", key=f"document_search_{document['group']}")
        matching = [key for key in members if document_query.casefold() in documents[key]["name"].casefold()]
        for member in paginated_items(matching, f"document_page_{document['group']}_{document_query}"):
            label = f"{'✓' if documents[member]['reviewed'] else '○'} {documents[member]['name']}"
            if st.button(label, key=f"open_document_{member}", type="primary" if member == identity else "secondary"):
                batch["active"] = member
                st.rerun()
        if not matching:
            st.caption("No matching documents.")
    previous_doc, current_doc, next_doc = st.columns([1, 3, 1])
    member_index = members.index(identity)
    if previous_doc.button("← Previous document", disabled=member_index == 0):
        batch["active"] = members[member_index - 1]
        st.rerun()
    current_doc.write(f"**{document['name']}** · Document {member_index + 1} of {len(members)}")
    if next_doc.button("Next document →", disabled=member_index == len(members) - 1):
        batch["active"] = members[member_index + 1]
        st.rerun()
    left, right = st.columns([1, 1.2])
    with left:
        st.caption(f"Detected with: {document['last_detection']} · Toggle Use to include or exclude detected fields.")
        if st.button("Detect fields again"):
            if mode == "OpenAI" and not api_key:
                st.error("Enter an OpenAI API key first.")
            else:
                try:
                    positions = [f for f in document["fields"] if f.get("kind") == "position"]
                    detected = detect_ai(document["bytes"], api_key, model) if mode == "OpenAI" else detect_rules(document["bytes"])
                    document["fields"] = detected + positions
                    document["last_detection"] = mode
                    document["preview_values"] = {}
                    document["preview_reset_nonce"] += 1
                    invalidate(document)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Detection failed: {exc}")
        editor_key = f"use_fields_{identity}_{document['preview_reset_nonce']}"
        if editor_key not in st.session_state or document.get("use_seed_nonce") != document["preview_reset_nonce"]:
            document["use_seed"] = copy.deepcopy(document["fields"])
            document["use_seed_nonce"] = document["preview_reset_nonce"]
        edited_fields = st.data_editor(
            pd.DataFrame(document["use_seed"], columns=["replace", "original", "placeholder"]),
            hide_index=True, disabled=["original", "placeholder"], num_rows="fixed",
            column_config={"replace": st.column_config.CheckboxColumn("Use"),
                           "original": st.column_config.TextColumn("Exact PDF text"),
                           "placeholder": st.column_config.TextColumn("Placeholder name")}, key=editor_key,
            on_change=commit_use_fields, args=(identity, editor_key))
        fields = [dict(field, replace=bool(use)) for field, use in zip(document["use_seed"], edited_fields["replace"])]
        if fields != document["fields"]:
            document["fields"] = fields
            invalidate(document)
        st.caption("Text fields replace all exact matching occurrences.")
        errors = field_errors(document)
        for error in errors:
            st.error(error)
        try:
            output, warnings = output_for(document)
            for warning in warnings:
                st.warning(warning)
        except Exception as exc:
            st.error(f"Could not render template: {exc}")
            output, warnings = None, []
        if len(members) > 1:
            st.caption("Apply this detected placeholder setup to the other documents in this type. "
                       "Copy Use settings and selected preview values. Unselected preview values on other documents stay unchanged. "
                       "Review is copied only when Reviewed and complete is checked here. Unmatched fields need individual review.")
            if st.button("Apply setup to other documents of this type", disabled=bool(errors) or output is None):
                total_applied = total_skipped = updated = 0
                for peer_id in members:
                    if peer_id == identity:
                        continue
                    peer = documents[peer_id]
                    try:
                        transferred, applied, skipped = apply_type_setup(document, peer)
                        if applied:
                            peer["fields"] = transferred
                            active_names = {normalize_name(f["placeholder"]) for f in transferred if f.get("replace")}
                            peer["preview_values"] = {
                                name: value for name, value in peer["preview_values"].items() if name in active_names}
                            peer["preview_values"].update({
                                name: value for name, value in document["preview_values"].items() if name in active_names})
                            peer["preview_reset_nonce"] += 1
                            invalidate(peer)
                            output_for(peer)
                            peer["reviewed"] = bool(document["reviewed"] and not skipped and not peer["error"] and not field_errors(peer))
                            updated += 1
                        total_applied += applied
                        total_skipped += skipped
                    except Exception as exc:
                        st.error(f"Could not apply setup to {peer['name']}: {exc}")
                batch["finished"] = False
                batch["apply_notice"] = f"Applied {total_applied} field settings across {updated} documents."
                if total_skipped:
                    batch["apply_notice"] += f" {total_skipped} unmatched fields still need individual review."
                st.rerun()
    with right:
        view = st.radio("Show", ["Template", "Original"], horizontal=True, key=f"view_{identity}")
        page_number = st.number_input("Page", min_value=1, max_value=document["page_count"],
                                      value=1, key=f"page_{identity}") - 1
        values = document["preview_values"]
        names = {normalize_name(f["placeholder"]) for f in fields if f.get("replace")}
        document["preview_values"] = values = {name: value for name, value in values.items() if name in names}
        if st.button("Clear selected preview values", disabled=not any(values.values())):
            document["preview_values"] = {name: "" for name in values}
            document["preview_reset_nonce"] += 1
            invalidate(document)
            st.rerun()
        if output is not None:
            preview_pdf = render_filled_template(output, values) if view == "Template" and values else output
            pages, targets = build_preview(preview_pdf if view == "Template" else document["bytes"],
                                           fields if view == "Template" else [],
                                           target_bytes=output if view == "Template" else None, page_number=page_number)
            # Use the corrected groups, rather than filename guesses, for sample recommendations.
            peers = {key: d for key, d in documents.items() if d["group"] == document["group"]}
            recommendations = {}
            for peer in peers.values():
                for field in peer["fields"]:
                    if field.get("replace") and field.get("original"):
                        name = normalize_name(field["placeholder"])
                        options = recommendations.setdefault(name, [])
                        if field["original"] not in options:
                            options.append(field["original"])
            event = pdf_preview(pages=pages, targets=targets, recommendations=recommendations if view == "Template" else {},
                                values=values if view == "Template" else {},
                                key=f"preview_{identity}_{page_number}_{view}_{document['preview_reset_nonce']}", default=None)
            if isinstance(event, dict) and view == "Template" and "kind" not in event and event != values:
                document["preview_values"] = event
                invalidate(document)
                st.rerun()
    st.divider()
    back, review, forward = st.columns([1, 2, 1])
    reviewed_key = f"reviewed_{identity}_{document['revision']}"
    st.markdown("""<style>
      .st-key-review_controls [data-testid="stCheckbox"] label p { font-size: 1.25rem; font-weight: 600; }
      .st-key-review_controls label[data-baseweb="checkbox"] > div:first-of-type {
        width: 28px; height: 28px; min-width: 28px;
      }
      .st-key-review_controls label[data-baseweb="checkbox"] { align-items: center; padding: 6px 0; }
    </style>""", unsafe_allow_html=True)
    with review.container(key="review_controls"):
        reviewed = st.checkbox("Reviewed and complete", value=document["reviewed"],
                               disabled=bool(errors) or output is None, key=reviewed_key,
                               on_change=update_reviewed, args=(identity, reviewed_key))
        document["reviewed"] = reviewed and not errors and output is not None
        if len(members) > 1:
            type_review_key = f"review_type_{identity}"
            st.session_state[type_review_key] = bool(document["reviewed"] and all(
                documents[member]["reviewed"] and not documents[member]["error"] for member in members))
            st.checkbox("Reviewed and complete for all documents of this type", key=type_review_key,
                        disabled=not document["reviewed"], on_change=update_type_reviewed,
                        args=(identity, type_review_key))
            st.caption("Check this document first, then mark the whole type complete. This does not change field settings.")
        if batch.get("review_notice"):
            st.warning(batch.pop("review_notice"))
    if back.button("Back"):
        move_stage(1)
    if forward.button("Save & Continue", type="primary"):
        move_stage(4)

elif batch["stage"] == 4:
    st.subheader("Review & Export")
    documents = batch["documents"]
    all_ready = True
    for group in batch["groups"]:
        members = [(identity, d) for identity, d in documents.items() if d["group"] == group]
        if not members:
            continue
        block_key = "review_export_" + hashlib.sha256(group.encode()).hexdigest()[:16]
        group_ready = True
        with st.container(key=block_key), st.expander(f"{group} · {group_status(group)}", expanded=True):
            for identity, document in members:
                errors = field_errors(document)
                ready = document["reviewed"] and not document["error"] and not errors
                all_ready = all_ready and ready
                group_ready = group_ready and ready
                st.write(f"{'✓' if ready else '○'} {document['name']} · {len(document['fields'])} fields")
                if st.button("Edit document", key=f"edit_{identity}"):
                    batch["active"] = identity
                    move_stage(3)
                try:
                    output, warnings = output_for(document)
                    for warning in errors + warnings:
                        st.warning(warning)
                except Exception as exc:
                    all_ready = False
                    group_ready = False
                    st.error(f"Could not render template: {exc}")
        if group_ready:
            st.markdown(f"""<style>
              .st-key-{block_key} [data-testid="stExpander"] details {{
                background-color: rgba(34, 197, 94, 0.10);
                border-color: rgba(34, 197, 94, 0.45);
              }}
              .st-key-{block_key} [data-testid="stExpander"] summary {{
                background-color: rgba(34, 197, 94, 0.08);
              }}
            </style>""", unsafe_allow_html=True)
    if not all_ready:
        st.info("Review and mark each document complete in step 2 before finishing.")
    if st.button("Back"):
        move_stage(3)
    if st.button("Finish", type="primary", disabled=not all_ready):
        archive = io.BytesIO()
        manifest = []
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as package:
            for index, (identity, document) in enumerate(documents.items(), 1):
                # Prefixes prevent collisions, including equal filenames in different groups.
                stem = re.sub(r"[^\w.-]", "_", Path(document["name"]).stem) or "document"
                group = re.sub(r"[^\w.-]", "_", document["group"]) or "type"
                prefix = f"{group}/{index:04d}_{stem}"
                output, warnings = output_for(document)
                package.writestr(prefix + "_template.pdf", output)
                package.writestr(prefix + "_fields.json", json.dumps(document["fields"], indent=2))
                manifest.append({"source": document["name"], "type": document["group"],
                                 "template": prefix + "_template.pdf", "warnings": warnings})
            package.writestr("manifest.json", json.dumps(manifest, indent=2))
        batch["archive"] = archive.getvalue()
        batch["finished"] = True
    if batch["finished"]:
        st.success("Batch complete. Your templates and field definitions are ready.")
        st.download_button("Download all templates (ZIP)", batch["archive"], file_name="pdf_templates.zip",
                           mime="application/zip", type="primary")

