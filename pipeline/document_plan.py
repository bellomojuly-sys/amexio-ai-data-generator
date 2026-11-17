"""Step 6 · Document plan: which documents get LLM text (contract v1.1 §7).

**Owner: Giulia.** Built after Dates & participants, when events have IDs. Per
case, one planned document per event that gets LLM text (performance appraisal,
termination letter, contract amendment; the other types stay templated), in
event order, with a key from code (``D01``, ``D02``, …), its type, its event and
its sections.

``CaseDocumentPlan`` is one case's plan (what ``write_document_text`` gets);
``DocumentPlan`` is the whole run.
"""

from __future__ import annotations

from case_model import Case

from .contracts import LLM_TEXT_DOCUMENTS, CaseDocumentPlan, CmIdOutput, DocumentPlan


def plan_case(case: Case) -> CaseDocumentPlan:
    documents = []
    for event_id in sorted(case.events):
        event = case.events[event_id]
        if event.type in LLM_TEXT_DOCUMENTS:
            doc_type, sections = LLM_TEXT_DOCUMENTS[event.type]
            documents.append({
                "doc": f"D{len(documents) + 1:02d}",
                "type": doc_type,
                "eventId": event_id,
                "sections": list(sections),
            })
    return CaseDocumentPlan.model_validate(
        {"employeeNumber": case.case_number, "documents": documents}
    )


def document_plan(cm: CmIdOutput) -> DocumentPlan:
    """Step 6: the plan for the whole run."""
    return DocumentPlan(plans=[plan_case(case) for case in cm.cases])
