"""Regression: IR decline with is_query_accepted=None must not crash main routing.

This test targets the exact failure seen in runtime logs:
- INPUT_RETRIEVAL_GRAPH returns a decline path where `is_query_accepted` is null.
- Main graph conditional router previously returned None, causing KeyError(None).

We validate `route_after_ir(...)` maps this safely to False (END path).
"""

from __future__ import annotations

from graphs.main_graph import route_after_ir


def test_route_after_ir_handles_none_as_decline() -> None:
    state = {
        "is_query_accepted": None,
        "decline_message": "Not a GIS query.",
    }
    assert route_after_ir(state) is False


def test_route_after_ir_true_only_for_explicit_true() -> None:
    assert route_after_ir({"is_query_accepted": True}) is True
    assert route_after_ir({"is_query_accepted": False}) is False
    assert route_after_ir({}) is False

