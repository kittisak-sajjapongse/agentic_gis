"""Workflow scenario: backend restart preserves session and layer state.

UI narrative:
1. User creates a session and imports a catalog layer from the UI.
2. Backend process restarts.
3. User refreshes UI; app should still show previous session layers via
   `GET /api/sessions/{sessionId}/layers` without re-importing.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app


def test_workflow_persistence_restart_state(monkeypatch, tmp_path) -> None:
    state_file = tmp_path / "poc_state.json"
    monkeypatch.setenv("POC_STATE_FILE", str(state_file))

    # First backend lifecycle: create session and import one layer.
    app1 = create_app()
    c1 = TestClient(app1)
    session_id = c1.post("/api/sessions", json={}).json()["sessionId"]
    catalog = c1.get("/api/catalog").json()["items"]
    assert catalog
    item_id = catalog[0]["catalogItemId"]
    imported = c1.post(
        f"/api/sessions/{session_id}/layers/import",
        json={"catalogItemId": item_id},
    )
    assert imported.status_code == 200, imported.text
    imported_layer_id = imported.json()["id"]

    # Simulate backend restart: new app instance reads same state file.
    app2 = create_app()
    c2 = TestClient(app2)
    listed = c2.get(f"/api/sessions/{session_id}/layers")
    assert listed.status_code == 200, listed.text
    layers = listed.json()["layers"]
    assert any(layer["id"] == imported_layer_id for layer in layers)

