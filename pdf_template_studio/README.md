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

The image preview supports clickable placeholders: choose sample values collected from documents in the same corrected group or enter a custom value. Selected values are included in both the preview and exported PDFs. Fields left as Keep as template retain their placeholders.

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




Sync also copies explicitly selected preview values (recommended or custom) alongside Use settings. Fields with no source preview selection retain their existing target selection. Choosing Keep as template, or clearing selected preview values, explicitly resets those selections and can be synced. Preview edits clear reviewed status. ZIP exports include selected values exactly as rendered in the edited preview. Unselected fields retain placeholders.


The enlarged review controls sit beside Save & Continue. Check Reviewed and complete for the current document to enable Reviewed and complete for all documents of this type. The second checkbox marks valid, successfully rendered peers reviewed without copying their fields. Unchecking it clears peer review while keeping the current document checked. Editing a document still clears its own completion status. Step transitions request a scroll to the top of the page.

## Portkey / Fontys models

In Detection settings, choose **Portkey**, enter your **Portkey API key** in the password field, and select a **Model slug**:

- `fontys-haiku-5-5`
- `claude-opus-5-5`
- `fontys-claude-sonnet-5-5`
- **Custom slug** to enter another exact alias available to your account.

The provided slugs are sent unchanged; availability is determined by your Portkey account/routing configuration. Under **Portkey routing (optional)**, enter a config ID if required by your institution. The integration uses `https://api.portkey.ai/v1/chat/completions` with `x-portkey-api-key` and optional `x-portkey-config`, following the chat contract in https://github.com/r-huijts/portkeytester.

You can instead set `PORTKEY_API_KEY` and optionally `PORTKEY_CONFIG_ID` in the environment before starting Streamlit. Keys are not written to project files or exports. Do not paste a real key into source code or commit it to GitHub.

After selecting the model, use **Select and organize PDFs** for new documents or **Detect fields again** for an existing document. Re-running detection replaces existing text-field choices and clears review. Simply switching the model does not automatically reprocess an already processed batch. The detected-with caption records the selected provider and slug. Offline detection and direct OpenAI remain available.

Portkey requests rely on the prompt for JSON rather than OpenAI-specific JSON-mode parameters, then validate the returned field list. HTTP authentication, access, routing, and quota errors are shown without exposing request headers. No extra Python packages are needed for Portkey.

Run `python -m unittest test_ai_gateway` for mocked gateway tests and `python test_wizard.py` for wizard regression checks. These checks do not call paid model APIs; live model access requires your key.

Generated placeholders use standard fonts with reliable braces and text extraction rather than reusing embedded PDF subsets. Preview values use an embedded fallback font when the standard font lacks a character. Hitboxes follow page rotation and grow to include longer filled values. Clickable regions highlight on hover or keyboard focus without persistent outlines; preview updates preserve the viewer scroll position. Unsupported glyphs in the original source PDF or characters outside the fallback font still require inspection. Run python -m unittest test_pdf_rendering to check embedded-font sources, Unicode replacements, rotation, and target bounds.

Exported template PDFs retain placeholders for fields marked Use, matching the exported field definitions. Selected preview values and custom preview text appear only on screen. The review step validates the reusable template before export. Unicode preview fonts are reused per page and subset before saving.


Text replacement removes the old characters without painting white background rectangles or leaving redaction annotations. This preserves existing colored backgrounds and avoids box artifacts in the exported PDF.
