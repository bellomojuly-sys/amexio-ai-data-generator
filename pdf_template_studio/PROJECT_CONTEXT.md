# PDF Template Studio — Project Context

## Project goal

Build a Python application that converts uploaded example PDFs into reusable PDF templates using AI.

The application does NOT generate mock data. It only creates, edits, previews, and exports document templates.

## Current technology

- Python
- Streamlit for the user interface
- PyMuPDF for PDF processing and preview
- OpenAI API for identifying variable values
- Pandas for editable field tables

## Current functionality

- Upload PDF documents
- Detect variable values using AI or basic field detection
- Convert values into placeholders such as `{{EMPLOYEE_NAME}}`
- Review and edit detected placeholders
- Generate and download PDF templates

## Planned application workflow

Implement a four-stage wizard:

1. **Select Documents:** Select multiple PDFs, show a file overview, and allow users to add or remove files.
2. **Upload & Organize:** Process the confirmed batch, identify document types, group related documents, and allow manual corrections.
3. **Edit Templates:** Navigate between document types using a searchable sidebar rather than a dropdown. Edit placeholders, add new fields, and preview the resulting PDF. Save changes when switching document types.
4. **Review & Export:** Review all templates, return to earlier steps when needed, and download the completed templates.

## Important requirements

- Do not automatically proceed when documents are selected.
- Use Back, Save & Continue, and Finish buttons.
- Support large batches of PDFs.
- Preserve individual documents within each document-type group.
- Preserve changes when switching between document types.
- Show completion status for each document type.
- Allow users to add new placeholder fields at specific positions in the PDF.
- Render PDF previews as images using PyMuPDF to avoid browser PDF embedding issues.
- Preserve original PDF layout as closely as possible.
- Keep existing working functionality.
- Eventually support saving and reopening unfinished batches.

## Development instructions

Inspect the existing code before making changes.

Implement changes incrementally, keeping the application functional.

Do not add mock data generation.

Test the application after changes and explain what was modified.