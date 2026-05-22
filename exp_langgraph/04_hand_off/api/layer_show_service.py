from __future__ import annotations

from pathlib import Path
from typing import Any

import geopandas as gpd

from api.layer_service import LayerService
from domain.state_models import LayerDescriptor, LayerPatchRequest, LayerSource, LayerStyle
from tools.artifact_provider import ArtifactProvider


class LayerShowService:
    """Source-of-truth service for "show layer" backend action."""

    def __init__(
        self,
        layer_service: LayerService,
        artifact_provider: ArtifactProvider,
        catalog_index: dict[str, dict[str, Any]],
        data_mount_dir: str,
    ) -> None:
        self._layer_service = layer_service
        self._artifact_provider = artifact_provider
        self._catalog_index = catalog_index
        self._data_mount_dir = Path(data_mount_dir)

    def show_layer(
        self,
        session_id: str,
        *,
        catalog_item_id: str | None = None,
        layer_id: str | None = None,
    ) -> LayerDescriptor:
        if (catalog_item_id is None) == (layer_id is None):
            raise ValueError("Provide exactly one of catalogItemId or layerId")

        if layer_id is not None:
            return self._show_existing_session_layer(session_id, layer_id)
        return self._show_catalog_item(session_id, catalog_item_id or "")

    def _show_existing_session_layer(self, session_id: str, layer_id: str) -> LayerDescriptor:
        existing = self._layer_service.get_layer(layer_id)
        if existing is None:
            raise KeyError("Layer not found")
        if not any(l.id == layer_id for l in self._layer_service.list_layers(session_id)):
            raise KeyError("Layer not found in session")
        if existing.visible:
            return existing
        updated = self._layer_service.update_layer(
            layer_id,
            LayerPatchRequest(visible=True),
        )
        if updated is None:
            raise KeyError("Layer not found")
        return updated

    def _show_catalog_item(self, session_id: str, catalog_item_id: str) -> LayerDescriptor:
        if catalog_item_id not in self._catalog_index:
            raise KeyError("Catalog item not found")

        for layer in self._layer_service.list_layers(session_id):
            if layer.catalogItemId == catalog_item_id:
                if layer.visible:
                    return layer
                updated = self._layer_service.update_layer(
                    layer.id,
                    LayerPatchRequest(visible=True),
                )
                if updated is None:
                    raise KeyError("Layer not found")
                return updated

        return self._import_catalog_item_as_layer(session_id, catalog_item_id)

    def _import_catalog_item_as_layer(self, session_id: str, catalog_item_id: str) -> LayerDescriptor:
        item = self._catalog_index[catalog_item_id]
        resolved = self._resolve_data_path(str(item.get("file", "")))
        if not resolved.exists() or not resolved.is_file():
            raise FileNotFoundError(f"Catalog file not found on backend host: {resolved}")

        source_artifact_id: str
        kind = "geojson"
        source_type = "geojson"
        style = LayerStyle(preset="line-default")
        suffix = resolved.suffix.lower()
        catalog_type = str(item.get("type", "")).upper()

        if catalog_type == "GEOTIFF" or suffix in {".tif", ".tiff"}:
            kind = "raster"
            source_type = "raster"
            style = LayerStyle(preset="raster-default")
            artifact = self._artifact_provider.register_artifact(
                path=str(resolved), content_type="image/tiff"
            )
            source_artifact_id = artifact.artifact_id
        elif catalog_type == "GEOPARQUET" or suffix == ".parquet":
            self._artifact_provider.register_artifact(
                path=str(resolved), content_type="application/vnd.apache.parquet"
            )
            geojson_path = self._convert_parquet_to_geojson(resolved)
            converted = self._artifact_provider.register_artifact(
                path=str(geojson_path), content_type="application/geo+json"
            )
            source_artifact_id = converted.artifact_id
        elif suffix == ".geojson":
            artifact = self._artifact_provider.register_artifact(
                path=str(resolved), content_type="application/geo+json"
            )
            source_artifact_id = artifact.artifact_id
        else:
            artifact = self._artifact_provider.register_artifact(
                path=str(resolved), content_type="application/octet-stream"
            )
            source_artifact_id = artifact.artifact_id

        layer = LayerDescriptor(
            id=self._layer_service.create_layer_id(prefix="lyr_in"),
            name=str(item.get("description", catalog_item_id)),
            kind=kind,  # type: ignore[arg-type]
            source=LayerSource(
                type=source_type,
                url=f"/api/artifacts/{source_artifact_id}/content",
            ),
            style=style,
            visible=True,
            origin="input",
            catalogItemId=catalog_item_id,
            createdAt=self._layer_service.now_iso(),
        )
        self._layer_service.add_layer(session_id, layer)
        return layer

    def _resolve_data_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if candidate.exists():
            return candidate
        if raw_path.startswith("/data/"):
            return self._data_mount_dir / raw_path.removeprefix("/data/")
        return candidate

    def _convert_parquet_to_geojson(self, parquet_path: Path) -> Path:
        gdf = gpd.read_parquet(parquet_path)
        output_path = parquet_path.with_name(f"{parquet_path.stem}.catalog.geojson")
        output_path.write_text(gdf.to_json(default=str), encoding="utf-8")
        return output_path

