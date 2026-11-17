# PDF Template Studio

Streamlit application for converting example PDFs into reusable PDF templates with `{{PLACEHOLDER}}` fields. It creates, edits, previews, and exports templates; it does not generate mock data.

## Run

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit (usually http://localhost:8501).

## Three-step workflow

1. **Select & Organize:** Select PDFs in **Add PDFs**; they remain visible there while you choose the batch. Manage the selection directly in **Add PDFs**; there is no separate selected-document list. Press **Select and organize PDFs** to detect fields and suggest document types. Correct type assignments in the table, then choose **Save & Continue**. Processing is explicit and does not begin on selection.
2. **Edit Templates:** Search document types in the sidebar. Above the editor, browse the searchable, paginated list of documents in the current type, or use **Previous document** and **Next document**. Toggle the fields table's **Use** column to include or exclude fields; original text and placeholder names are fixed. Fields cannot be added manually. Check the Original or Template preview and mark documents reviewed using the checkbox beside Save & Continue at the bottom of the editor. **Apply setup to other documents of this type** transfers settings using each document's own values and copies reviewed status to fully matched, valid, successfully rendered documents only when the source's Reviewed and complete checkbox is checked. Sync never checks the source's review box. Documents with unmatched fields still need review. A completed type shows a checkmark once all its documents are reviewed. Changing Use clears the reviewed checkbox and type checkmark immediately.
3. **Review & Export:** Inspect statuses and warnings and return to individual documents as needed. Individual PDF and JSON download buttons are not available. Once all documents are reviewed, choose **Finish** and download the ZIP containing all templates, field definitions, and a manifest.

Use **Back** to revisit earlier stages. Existing fields remain intact when re-confirming unchanged documents. Removing a document and confirming the batch deletes that document's edits. Re-running detection replaces its text replacement suggestions while preserving positioned fields.

The image preview supports clickable placeholders: choose sample values collected from documents in the same corrected group or enter a custom value. These values affect the preview only; template exports retain placeholders.

## State and performance

Work is retained in the current Streamlit session. Saving batches to disk and reopening them is not implemented yet. PDF preview images are generated one page at a time, and rendered templates are reused until fields change. Documents are processed sequentially with progress reporting; source bytes and rendered results remain in memory.

## Limitations

- Text-based PDFs only; no OCR for scanned PDFs. Encrypted or unreadable PDFs must be removed or corrected.
- Grouping is a heuristic and should be checked manually. Group members retain their own fields and source PDFs.
- Text replacement uses literal matches and can replace multiple occurrences. Split text and unusual PDF encodings may not match.
- Typography and layout are preserved where possible. Long placeholders, nonwhite backgrounds, rotated pages, and complex layouts require visual inspection. Previously created positioned fields remain supported when rendering existing session data.
- Offline detection recognizes common employment, medical, training, review, and payroll labels. OpenAI detection sends up to 500 extracted nonempty lines to the configured model; review its suggestions.
- API keys are entered in the sidebar or read from `OPENAI_API_KEY` and are not included in exports.

## Verification

```powershell
.venv\Scripts\python.exe test_wizard.py
```

The regression script uses in-memory example PDFs to check selection processing, Use-only field editing, document navigation, detection, redaction, existing positioned fields, state persistence, review gating, ZIP contents, and invalid-PDF isolation. It does not call OpenAI or automate browser clicks in the preview component.

Partial-word and overlapping matches are silently skipped by the renderer.




Sync also copies explicitly selected preview values (recommended or custom) alongside Use settings. Fields with no source preview selection retain their existing target selection. Choosing Keep as template, or clearing selected preview values, explicitly resets those selections and can be synced. Preview edits clear reviewed status. Template PDF and ZIP exports retain placeholders; selected values remain available in the preview.


The enlarged review controls sit beside Save & Continue. Check Reviewed and complete for the current document to enable Reviewed and complete for all documents of this type. The second checkbox marks valid, successfully rendered peers reviewed without copying their fields. Unchecking it clears peer review while keeping the current document checked. Editing a document still clears its own completion status. Step transitions request a scroll to the top of the page.
