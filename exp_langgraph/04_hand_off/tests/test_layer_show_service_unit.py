"""Unit tests for LayerShowService using lightweight stubs.

These tests intentionally avoid file I/O, artifact registration, geopandas,
and catalog parsing. They validate only orchestration behavior:
- selector validation
- show by existing layer id
- show by catalog id (reuse existing or import via dependency)
"""

from __future__ import annotations

from api.layer_service import LayerService
from api.layer_show_service import LayerShowService
from domain.state_models import LayerDescriptor, LayerSource, LayerStyle


class _StubImporter:
    def __init__(self, layer_service: LayerService):
        self.layer_service = layer_service
        self.calls: list[tuple[str, str]] = []

    def import_layer(self, session_id: str, catalog_item_id: str) -> LayerDescriptor:
        self.calls.append((session_id, catalog_item_id))
        layer = LayerDescriptor(
            id=self.layer_service.create_layer_id(prefix="lyr_in"),
            name=f"Imported {catalog_item_id}",
            kind="geojson",
            source=LayerSource(type="geojson", url="/api/artifacts/fake/content"),
            style=LayerStyle(preset="line-default"),
            visible=True,
            origin="input",
            catalogItemId=catalog_item_id,
            createdAt=self.layer_service.now_iso(),
        )
        self.layer_service.add_layer(session_id, layer)
        return layer


def _make_layer(layer_service: LayerService, *, visible: bool, catalog_item_id: str | None = None) -> LayerDescriptor:
    return LayerDescriptor(
        id=layer_service.create_layer_id(prefix="lyr_test"),
        name="Test layer",
        kind="geojson",
        source=LayerSource(type="geojson", url="/api/artifacts/fake/content"),
        style=LayerStyle(preset="line-default"),
        visible=visible,
        origin="input",
        catalogItemId=catalog_item_id,
        createdAt=layer_service.now_iso(),
    )


def test_show_layer_requires_exactly_one_selector() -> None:
    ls = LayerService()
    importer = _StubImporter(ls)
    svc = LayerShowService(ls, importer)

    try:
        svc.show_layer("sess", layer_id=None, catalog_item_id=None)
        raise AssertionError("Expected ValueError")
    except ValueError:
        pass

    try:
        svc.show_layer("sess", layer_id="lyr", catalog_item_id="cat_001")
        raise AssertionError("Expected ValueError")
    except ValueError:
        pass


def test_show_existing_layer_by_layer_id() -> None:
    ls = LayerService()
    ls.init_session("sess_a")
    layer = _make_layer(ls, visible=False)
    ls.add_layer("sess_a", layer)
    importer = _StubImporter(ls)
    svc = LayerShowService(ls, importer)

    shown = svc.show_layer("sess_a", layer_id=layer.id)
    assert shown.visible is True
    assert importer.calls == []


def test_show_catalog_reuses_existing_session_layer() -> None:
    ls = LayerService()
    ls.init_session("sess_b")
    layer = _make_layer(ls, visible=False, catalog_item_id="cat_001")
    ls.add_layer("sess_b", layer)
    importer = _StubImporter(ls)
    svc = LayerShowService(ls, importer)

    shown = svc.show_layer("sess_b", catalog_item_id="cat_001")
    assert shown.id == layer.id
    assert shown.visible is True
    assert importer.calls == []


def test_show_catalog_imports_when_missing() -> None:
    ls = LayerService()
    ls.init_session("sess_c")
    importer = _StubImporter(ls)
    svc = LayerShowService(ls, importer)

    shown = svc.show_layer("sess_c", catalog_item_id="cat_999")
    assert shown.catalogItemId == "cat_999"
    assert shown.visible is True
    assert importer.calls == [("sess_c", "cat_999")]

