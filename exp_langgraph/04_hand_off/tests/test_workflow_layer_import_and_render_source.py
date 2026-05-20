"""Workflow scenario: user imports catalog layer and UI map receives render source.

UI narrative:
1. User opens catalog panel; UI calls `GET /api/catalog`.
2. User clicks Import on a GeoParquet catalog item.
3. UI calls `POST /api/sessions/{sessionId}/layers/import`.
4. UI reloads `GET /api/sessions/{sessionId}/layers` and obtains an imported
   layer whose source points to an artifact URL suitable for map loading.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app


def test_workflow_layer_import_and_render_source() -> None:
    app = create_app()
    client = TestClient(app)

    session_id = client.post("/api/sessions", json={}).json()["sessionId"]
    catalog = client.get("/api/catalog").json()["items"]
    assert isinstance(catalog, list) and len(catalog) > 0

    # Pick first GeoParquet item to validate conversion-backed render source.
    geoparquet_items = [i for i in catalog if str(i.get("type", "")).upper() == "GEOPARQUET"]
    assert geoparquet_items, "Expected at least one GEOPARQUET catalog item"
    item_id = geoparquet_items[0]["catalogItemId"]

    imported = client.post(
        f"/api/sessions/{session_id}/layers/import",
        json={"catalogItemId": item_id},
    )
    assert imported.status_code == 200, imported.text
    layer = imported.json()
    assert layer["origin"] == "input"
    assert layer["source"]["type"] == "geojson"
    assert str(layer["source"]["url"]).startswith("/api/artifacts/")

    # Imported layer is discoverable via session list (what UI panel uses).
    listed = client.get(f"/api/sessions/{session_id}/layers")
    assert listed.status_code == 200, listed.text
    layers = listed.json()["layers"]
    assert any(l["id"] == layer["id"] for l in layers)

