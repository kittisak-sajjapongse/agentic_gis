"""Workflow scenario: user toggles visibility for an agent-created output layer.

UI narrative:
1. Agent run produces an output layer and it appears in layer panel.
2. User clicks the visibility checkbox off/on in the UI.
3. UI sends `PATCH /api/layers/{layerId}` with `visible` flag changes.
4. Backend persists state; subsequent `GET /api/sessions/{sessionId}/layers`
   returns the latest visibility values.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app
from domain.state_models import LayerDescriptor, LayerSource, LayerStyle


def test_workflow_agent_output_layer_visibility_toggle() -> None:
    app = create_app()
    client = TestClient(app)

    session_id = client.post("/api/sessions", json={}).json()["sessionId"]
    layer_service = app.state.layer_service

    # Simulate post-run state where an agent already created one output layer.
    layer = LayerDescriptor(
        id=layer_service.create_layer_id(prefix="lyr_out"),
        name="Simulated agent output",
        kind="geojson",
        source=LayerSource(type="geojson", url="/api/artifacts/fake/content"),
        style=LayerStyle(preset="line-default"),
        visible=True,
        origin="agent_output",
        createdByRunId="run_sim",
        createdAt=layer_service.now_iso(),
    )
    layer_service.add_layer(session_id, layer)

    off = client.patch(f"/api/layers/{layer.id}", json={"visible": False})
    assert off.status_code == 200, off.text
    assert off.json()["visible"] is False

    on = client.patch(f"/api/layers/{layer.id}", json={"visible": True})
    assert on.status_code == 200, on.text
    assert on.json()["visible"] is True

    listed = client.get(f"/api/sessions/{session_id}/layers")
    assert listed.status_code == 200, listed.text
    fetched = [l for l in listed.json()["layers"] if l["id"] == layer.id]
    assert fetched and fetched[0]["visible"] is True

