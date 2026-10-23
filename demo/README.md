# AMEXIO demo: one synthetic claim, end to end

All data in this folder is fictional and marked AI-GENERATED FAKE DATA / DataType = SYNTHETIC.

## What is here

| Path | What it is |
| --- | --- |
| `AMEXIO_demo_walkthrough.html` | Offline copy of the clickable walkthrough. Double-click to open. Needs internet only for the fonts. |
| `dossier_generated/` | The dossier as "generated": config, cast (personas), storyline, 5 documents + metadata. Contains one planted error. |
| `dossier_fixed/` | Same dossier after correcting EVT-002. Includes `export/` with `import.xml`. |
| `validate_and_export.py` | The rule-based validator and XML exporter that produced the reports. Plain Python 3, no packages needed. |
| `stage_prompts.md` | Draft prompts for the personas, storyline and document steps. |

## The planted error

In `dossier_generated/storyline.json`, event EVT-002 ("Claim submitted") is dated
12 March 2026, two days before the accident (EVT-001, 14 March 2026).
The claim form (DOC-002) and the acknowledgement letter (DOC-003) both use that date.

## Running the validator yourself

```
python validate_and_export.py dossier_generated   # 1 error, export blocked
python validate_and_export.py dossier_fixed       # all checks pass, writes dossier_fixed/export/
```

## Presenting

Use the arrow keys or a presentation clicker (Page Up / Page Down) to move between steps.
Press N for presenter notes. "Reset demo" in the top right puts the error back.

Suggested flow (about 5 minutes):
1. Overview: the AI writes content, code keeps the facts.
2. Configure: this is our assumed config; metadata fields wait on AMEXIO's mock data.
3. Personas & storyline: IDs, review point. Don't point out the date yet.
4. Documents: toggle the highlighting to show which values came from the model.
5. Validate: run it, the timeline check fails, apply the fix, run again.
6. Export: folder + XML in the Content Server Object Importer shape (attribute names are placeholders).
7. Questions: collect answers.

## Assumptions to say out loud

- Metadata fields, category names and attribute names are our guesses until AMEXIO shares its schema.
- The XML follows the general shape of the Content Server Object Importer (`<import>` / `<node type=... action="create">`).
- The content was written with an AI assistant ahead of time; nothing calls an AI live.
