"""Workflow scenario: UI/agent-triggered show-layer endpoint drives map visibility.

UI narrative:
1. User asks to show a known layer (future: via agent action; current: direct API).
2. Backend receives `POST /api/sessions/{sessionId}/layers/show`.
3. If request uses `catalogItemId`:
   - backend imports the layer into session if missing,
   - ensures `visible=true`,
   - returns resolved layer descriptor.
4. If request uses `layerId`:
   - backend toggles existing session layer visibility to true.
5. UI then refreshes session layers and map reflects visible layer.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app


def test_workflow_show_layer_endpoint_catalog_and_layer_id() -> None:
    app = create_app()
    client = TestClient(app)

    session_id = client.post("/api/sessions", json={}).json()["sessionId"]
    catalog = client.get("/api/catalog").json()["items"]
    assert catalog and isinstance(catalog, list)
    catalog_item_id = catalog[0]["catalogItemId"]

    # 1) Show by artifact imports if missing and returns visible layer.
    show1 = client.post(
        f"/api/sessions/{session_id}/layers/show",
        json={"artifact": catalog_item_id},
    )
    assert show1.status_code == 200, show1.text
    layer = show1.json()
    assert layer["visible"] is True
    assert layer["catalogItemId"] == catalog_item_id
    layer_id = layer["id"]

    # 2) Repeat show by same catalog id should resolve existing session layer (no duplicate).
    show2 = client.post(
        f"/api/sessions/{session_id}/layers/show",
        json={"catalogItemId": catalog_item_id},
    )
    assert show2.status_code == 200, show2.text
    layer2 = show2.json()
    assert layer2["id"] == layer_id

    listed = client.get(f"/api/sessions/{session_id}/layers").json()["layers"]
    same_catalog = [l for l in listed if l.get("catalogItemId") == catalog_item_id]
    assert len(same_catalog) == 1

    # 3) Hide then show by layer id should toggle visible back to true.
    patch = client.patch(f"/api/layers/{layer_id}", json={"visible": False})
    assert patch.status_code == 200 and patch.json()["visible"] is False

    show3 = client.post(
        f"/api/sessions/{session_id}/layers/show",
        json={"layerId": layer_id},
    )
    assert show3.status_code == 200, show3.text
    assert show3.json()["visible"] is True


def test_workflow_show_layer_endpoint_invalid_ids() -> None:
    app = create_app()
    client = TestClient(app)
    session_id = client.post("/api/sessions", json={}).json()["sessionId"]

    bad_catalog = client.post(
        f"/api/sessions/{session_id}/layers/show",
        json={"catalogItemId": "cat_999999"},
    )
    assert bad_catalog.status_code == 404

    bad_layer = client.post(
        f"/api/sessions/{session_id}/layers/show",
        json={"layerId": "lyr_missing"},
    )
    assert bad_layer.status_code == 404
