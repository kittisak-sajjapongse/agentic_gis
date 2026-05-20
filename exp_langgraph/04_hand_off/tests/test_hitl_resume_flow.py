from __future__ import annotations

"""
QA-003 automated regression for HITL clarification/resume flow.

Scope:
- Validates run interruption -> clarification_required event -> resume -> completion.
- Uses RunService directly with a monkeypatched graph builder.
- Deterministic and fast for local regression runs.
"""

import asyncio

import api.run_service as run_service_module
from api.run_service import RunService


class FakeInterrupt:
    def __init__(self, interrupt_id: str, value: dict):
        self.id = interrupt_id
        self.value = value


class FakeStateInterrupt:
    def __init__(self):
        self.values = {}
        self.interrupts = [
            FakeInterrupt(
                "intr_hitl_1",
                {
                    "type": "ir_clarification",
                    "question": "Which month in 2025 should be used?",
                },
            )
        ]


class FakeStateDone:
    def __init__(self):
        self.values = {"outputs": []}
        self.interrupts = []


class FakeGraph:
    def __init__(self):
        self._calls = 0

    async def astream(self, inputs, config=None):
        self._calls += 1
        await asyncio.sleep(0.01)
        if False:
            yield None

    async def aget_state(self, config=None):
        if self._calls == 1:
            return FakeStateInterrupt()
        return FakeStateDone()


async def _fake_build_main_graph():
    return FakeGraph()


async def _collect_until_terminal(rs: RunService, run_id: str) -> list[str]:
    event_types: list[str] = []
    async for event in rs.subscribe(run_id):
        event_types.append(event["type"])
        if event["type"] in {"clarification_required", "done", "error"}:
            break
    return event_types


async def _run_test_impl() -> None:
    original_builder = run_service_module.build_main_graph
    run_service_module.build_main_graph = _fake_build_main_graph

    try:
        rs = RunService()
        run = rs.create_run("sess_hitl")

        # 1) First pass should interrupt for clarification.
        events_first_task = asyncio.create_task(_collect_until_terminal(rs, run.runId))
        await asyncio.sleep(0)
        await rs.execute_run("sess_hitl", run.runId, "Show hotspot in 2025")
        first_events = await events_first_task

        status_1 = rs.get_run(run.runId)
        assert status_1 is not None
        assert status_1.status == "interrupted", status_1.status
        assert status_1.pendingInterruptId == "intr_hitl_1"
        assert "clarification_required" in first_events, first_events

        # 2) Resume should complete the run.
        await rs.resume_run(run.runId, "intr_hitl_1", "Use March 2025")
        second_events = await _collect_until_terminal(rs, run.runId)

        status_2 = rs.get_run(run.runId)
        assert status_2 is not None
        assert status_2.status == "completed", status_2.status
        assert "done" in second_events, second_events

        # 3) Wrong interrupt id should fail.
        try:
            await rs.resume_run(run.runId, "wrong_interrupt", "answer")
            raise AssertionError("Expected ValueError for wrong interruptId")
        except ValueError:
            pass

        print("PASS: HITL interrupt/resume flow works")
        print(f"run_id={run.runId} first_events={first_events} second_events={second_events}")
    finally:
        run_service_module.build_main_graph = original_builder


def test_hitl_resume_flow() -> None:
    asyncio.run(_run_test_impl())
