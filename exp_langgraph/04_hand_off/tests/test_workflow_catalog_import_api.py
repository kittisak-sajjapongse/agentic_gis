"""Integration-style API test for BACKEND-007 catalog import endpoints.

Covers:
1) GET /api/catalog returns stable catalog item ids.
2) POST /api/sessions creates a session.
3) POST /api/sessions/{sessionId}/layers/import imports a catalog dataset.
4) GET /api/sessions/{sessionId}/layers includes imported layer.
5) GET /api/artifacts/{artifactId}/content is readable for imported source.
"""

from __future__ import annotations

from pathlib import Path
import sys

from fastapi.testclient import TestClient

# Allow direct execution: `python3 tests/test_workflow_*.py`
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.app import create_app
from domain.gis_catalog import GIS_COLLECTION


def _extract_artifact_id_from_source_url(url: str) -> str:
    # Expected pattern: /api/artifacts/{artifact_id}/content
    parts = [p for p in url.split("/") if p]
    assert len(parts) >= 4 and parts[0] == "api" and parts[1] == "artifacts"
    return parts[2]


def main() -> None:
    app = create_app()
    client = TestClient(app)

    # 1) Catalog listing
    catalog_resp = client.get("/api/catalog")
    assert catalog_resp.status_code == 200, catalog_resp.text
    catalog_payload = catalog_resp.json()
    assert "items" in catalog_payload and isinstance(catalog_payload["items"], list)
    assert len(catalog_payload["items"]) == len(GIS_COLLECTION)
    first_item = catalog_payload["items"][0]
    catalog_item_id = first_item.get("catalogItemId")
    assert isinstance(catalog_item_id, str) and catalog_item_id.startswith("cat_")

    # 2) Session creation
    session_resp = client.post("/api/sessions", json={})
    assert session_resp.status_code == 200, session_resp.text
    session_id = session_resp.json()["sessionId"]
    assert isinstance(session_id, str) and session_id.startswith("sess_")

    # 3) Import catalog layer into session
    import_resp = client.post(
        f"/api/sessions/{session_id}/layers/import",
        json={"catalogItemId": catalog_item_id},
    )
    assert import_resp.status_code == 200, import_resp.text
    imported_layer = import_resp.json()
    assert imported_layer["origin"] == "input"
    assert imported_layer["id"].startswith("lyr_in_")
    source_url = imported_layer["source"]["url"]
    assert isinstance(source_url, str) and source_url.startswith("/api/artifacts/")

    # 4) Session layer list reflects imported layer
    layers_resp = client.get(f"/api/sessions/{session_id}/layers")
    assert layers_resp.status_code == 200, layers_resp.text
    layers = layers_resp.json()["layers"]
    assert any(layer["id"] == imported_layer["id"] for layer in layers)

    # 5) Artifact content endpoint is readable
    artifact_id = _extract_artifact_id_from_source_url(source_url)
    artifact_resp = client.get(f"/api/artifacts/{artifact_id}/content")
    assert artifact_resp.status_code == 200, artifact_resp.text
    assert len(artifact_resp.content) > 0

    print(
        "PASS: catalog import API flow works",
        f"session_id={session_id}",
        f"catalog_item_id={catalog_item_id}",
        f"layer_id={imported_layer['id']}",
    )


if __name__ == "__main__":
    main()
