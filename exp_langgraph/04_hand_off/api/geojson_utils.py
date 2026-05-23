from __future__ import annotations

import json
import logging
from pathlib import Path

import geopandas as gpd
from pyproj import CRS


def normalize_geojson_to_epsg4326(
    geojson_path: Path,
    *,
    logger: logging.Logger,
    output_suffix: str = ".epsg4326.geojson",
    log_prefix: str = "GeoJSON",
) -> Path | None:
    """Normalize GeoJSON geometry CRS to EPSG:4326 for MapLibre rendering.

    Returns:
    - New normalized file path when reprojection was performed.
    - None when already EPSG:4326 or CRS cannot be resolved safely.
    """
    try:
        gdf = gpd.read_file(geojson_path)

        if gdf.crs is None:
            payload = json.loads(geojson_path.read_text(encoding="utf-8"))
            crs_name = payload.get("crs", {}).get("properties", {}).get("name")
            if crs_name:
                try:
                    gdf = gdf.set_crs(CRS.from_user_input(crs_name))
                except Exception:
                    logger.warning(
                        "%s declared unparseable CRS=%s path=%s; keeping original geometry",
                        log_prefix,
                        crs_name,
                        str(geojson_path),
                    )

        if gdf.crs is None:
            logger.warning("%s missing CRS path=%s; cannot normalize", log_prefix, str(geojson_path))
            return None

        if str(gdf.crs).upper() == "EPSG:4326":
            return None

        transformed = gdf.to_crs(epsg=4326)
        output_path = geojson_path.with_name(f"{geojson_path.stem}{output_suffix}")
        output_path.write_text(transformed.to_json(default=str), encoding="utf-8")
        logger.info(
            "Normalized %s CRS to EPSG:4326 source=%s output=%s",
            log_prefix,
            str(geojson_path),
            str(output_path),
        )
        return output_path
    except Exception:
        logger.exception("Failed to normalize %s CRS path=%s", log_prefix, str(geojson_path))
        return None

