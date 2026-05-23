"""Workflow scenario: UI receives `layer_updated` without full layer-list polling.

UI narrative:
1. User has an active run stream open for a session.
2. A layer state changes via REST mutation (`PATCH /api/layers/{id}`) or
   show-layer workflow (`POST /api/sessions/{id}/layers/show`).
3. Backend emits `layer_updated` on the active run stream.
4. UI patches local layer state directly from SSE payload.
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from api.app import create_app
from domain.state_models import LayerDescriptor, LayerSource, LayerStyle


def test_workflow_patch_emits_layer_updated_sse() -> None:
    app = create_app()
    client = TestClient(app)

    session_id = client.post("/api/sessions", json={}).json()["sessionId"]
    run_service = app.state.run_service
    layer_service = app.state.layer_service
    run = run_service.create_run(session_id)

    layer = LayerDescriptor(
        id=layer_service.create_layer_id(prefix="lyr_out"),
        name="Toggle target",
        kind="geojson",
        source=LayerSource(type="geojson", url="/api/artifacts/fake/content"),
        style=LayerStyle(preset="line-default"),
        visible=True,
        origin="agent_output",
        createdByRunId="run_sim",
        createdAt=layer_service.now_iso(),
    )
    layer_service.add_layer(session_id, layer)

    async def _collect() -> dict:
        async for event in run_service.subscribe(run.runId):
            if event["type"] == "layer_updated":
                return event
        raise AssertionError("Expected layer_updated event")

    async def _run() -> dict:
        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)
        resp = client.patch(f"/api/layers/{layer.id}", json={"visible": False})
        assert resp.status_code == 200, resp.text
        return await asyncio.wait_for(task, timeout=3.0)

    event = asyncio.run(_run())
    assert event["payload"]["layerId"] == layer.id
    assert event["payload"]["changed"] == {"visible": False}


def test_workflow_show_endpoint_emits_layer_updated_sse() -> None:
    app = create_app()
    client = TestClient(app)

    session_id = client.post("/api/sessions", json={}).json()["sessionId"]
    run_service = app.state.run_service
    layer_service = app.state.layer_service
    run = run_service.create_run(session_id)

    layer = LayerDescriptor(
        id=layer_service.create_layer_id(prefix="lyr_in"),
        name="Hidden catalog layer",
        kind="geojson",
        source=LayerSource(type="geojson", url="/api/artifacts/fake/content"),
        style=LayerStyle(preset="line-default"),
        visible=False,
        origin="input",
        catalogItemId="cat_001",
        createdAt=layer_service.now_iso(),
    )
    layer_service.add_layer(session_id, layer)

    async def _collect() -> dict:
        async for event in run_service.subscribe(run.runId):
            if event["type"] == "layer_updated":
                return event
        raise AssertionError("Expected layer_updated event")

    async def _run() -> dict:
        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)
        resp = client.post(
            f"/api/sessions/{session_id}/layers/show",
            json={"artifact": layer.id},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["visible"] is True
        return await asyncio.wait_for(task, timeout=3.0)

    event = asyncio.run(_run())
    assert event["payload"]["layerId"] == layer.id
    assert event["payload"]["changed"] == {"visible": True}


def test_workflow_import_endpoint_emits_layer_updated_sse() -> None:
    app = create_app()
    client = TestClient(app)

    session_id = client.post("/api/sessions", json={}).json()["sessionId"]
    run_service = app.state.run_service
    run = run_service.create_run(session_id)

    catalog = client.get("/api/catalog")
    assert catalog.status_code == 200, catalog.text
    items = catalog.json().get("items", [])
    assert items and isinstance(items, list)
    catalog_item_id = items[0]["catalogItemId"]

    async def _collect() -> dict:
        async for event in run_service.subscribe(run.runId):
            if event["type"] == "layer_updated":
                return event
        raise AssertionError("Expected layer_updated event")

    async def _run() -> dict:
        task = asyncio.create_task(_collect())
        await asyncio.sleep(0)
        resp = client.post(
            f"/api/sessions/{session_id}/layers/import",
            json={"catalogItemId": catalog_item_id},
        )
        assert resp.status_code == 200, resp.text
        return await asyncio.wait_for(task, timeout=3.0)

    event = asyncio.run(_run())
    assert event["payload"]["changed"].get("visible") is True
