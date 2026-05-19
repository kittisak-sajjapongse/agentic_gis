from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_normalize_fn():
    module_path = Path(__file__).resolve().parents[1] / "agents" / "ir_normalization.py"
    spec = spec_from_file_location("ir_normalization", module_path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.normalize_ir_response


normalize_ir_response = _load_normalize_fn()


def test_decline_message_fallback_when_rejected_and_missing_reason() -> None:
    normalized = normalize_ir_response(
        {
            "is_query_accepted": False,
            "decline_message": None,
            "clarification_question": None,
        }
    )
    assert normalized["is_query_accepted"] is False
    assert isinstance(normalized["decline_message"], str)
    assert normalized["decline_message"]


def test_accepted_clears_decline_message() -> None:
    normalized = normalize_ir_response(
        {
            "is_query_accepted": True,
            "decline_message": "some stale reason",
            "clarification_question": None,
        }
    )
    assert normalized["is_query_accepted"] is True
    assert normalized["decline_message"] is None


def test_clarification_forces_accepted_to_none() -> None:
    normalized = normalize_ir_response(
        {
            "is_query_accepted": False,
            "decline_message": "x",
            "clarification_question": "Need area/time range?",
        }
    )
    assert normalized["clarification_question"] == "Need area/time range?"
    assert normalized["is_query_accepted"] is None
