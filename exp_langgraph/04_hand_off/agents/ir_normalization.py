from __future__ import annotations

from typing import Any


def normalize_ir_response(resp: dict[str, Any]) -> dict[str, Any]:
    """Normalize IR response invariants for stable downstream behavior.

    Invariants:
    1) accepted=True  => decline_message=None
    2) accepted=False => decline_message must be non-empty (fallback if missing)
    3) clarification_question present => accepted=None
    """
    normalized = dict(resp)
    accepted = normalized.get("is_query_accepted")
    question = normalized.get("clarification_question")
    decline = normalized.get("decline_message")

    if isinstance(question, str) and question.strip():
        normalized["is_query_accepted"] = None
        accepted = None

    if accepted is True:
        normalized["decline_message"] = None
    elif accepted is False:
        if not isinstance(decline, str) or not decline.strip():
            normalized["decline_message"] = (
                "Request was not accepted, but no decline reason was provided by the model."
            )
        else:
            normalized["decline_message"] = decline.strip()

    return normalized

