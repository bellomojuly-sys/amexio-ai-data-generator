"""Deterministic answers for ``FakeLLM`` that fit whatever the chain asks.

``FakeLLM(answer)`` reads the ``<request>`` of each prompt and returns a valid
answer: names for Personas, text for every slot of Event content, text for
every planned section of Document text. Used by ``options.fake_llm`` runs and by
the chain tests, so the whole chain runs offline, without an API key.
"""

from __future__ import annotations

from .generation import request_of

FIRST = ["Sanne", "Daan", "Fatima", "Lucas", "Noor", "Milan", "Emma", "Yusuf", "Lotte", "Sem"]
LAST = ["Jansen", "de Boer", "El Amrani", "Visser", "Smit", "Mulder", "Bos", "Yilmaz", "Peters", "Vos"]


def answer(prompt: str) -> dict:
    request = request_of(prompt)
    task = request["task"]
    if task == "personas":
        positions = [(d["name"], p) for d in request["departments"] for p in d["positions"]]
        return {"employees": [
            {"firstName": FIRST[i % len(FIRST)], "lastName": LAST[(i * 3) % len(LAST)],
             "department": positions[i % len(positions)][0],
             "position": positions[i % len(positions)][1]}
            for i in range(request["count"])
        ]}
    if task == "event_content":
        return {"content": [
            {"employeeNumber": e["employeeNumber"],
             "slots": [_slot_text(s, e["people"]) for s in e["slots"]]}
            for e in request["employees"]
        ]}
    if task == "document_text":
        employee = _person(request["people"], "employee")
        return {"employeeNumber": request["employeeNumber"], "documents": [
            {"doc": d["doc"], "sections": {
                section: f"On {d['date']}, this {section.replace('_', ' ')} concerns {employee}."
                for section in d["sections"]
            }}
            for d in request["documents"]
        ]}
    raise ValueError(f"FakeLLM: unknown task {task!r}")


def _person(people, role):
    return next((p["placeholder"] for p in people if p["role"] == role), people[0]["placeholder"])


def _slot_text(slot: dict, people: list[dict]) -> dict:
    employee = _person(people, "employee")
    kind = slot["type"]
    out = {"slot": slot["slot"], "summary": f"{kind.replace('_', ' ').capitalize()} event."}
    if kind == "training":
        out["course"] = "Secure Coding Fundamentals"
    elif kind == "appraisal":
        out["comment"] = f"{employee} delivered the year's goals; rating: {slot['rating']}."
    elif kind == "contract_change":
        out["reason"] = {"promotion": "Promotion", "made_permanent": "Contract made permanent",
                         "hours_change": "Change of working hours"}.get(slot["change"],
                                                                       "Annual salary review")
    return out
