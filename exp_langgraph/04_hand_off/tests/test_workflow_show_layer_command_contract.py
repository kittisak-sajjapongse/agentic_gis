"""Workflow scenario: chat asks agent to show a known layer deterministically.

UI narrative (target behavior after EPIC-LAYERSHOW-001 implementation):
1. User types "show hotspot 2025 layer" in chat panel.
2. Agent resolves intent to a stable layer identifier (catalog or session).
3. Backend executes explicit show-layer command contract.
4. UI receives update event and layer becomes visible on map without manual import.

Status:
- This workflow is not implemented yet in current POC.
- Test is intentionally skipped until the API/service contract is delivered.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="Pending EPIC-LAYERSHOW-001 implementation.")
def test_workflow_show_layer_command_contract() -> None:
    pass

