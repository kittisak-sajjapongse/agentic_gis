#!/usr/bin/env python3
import argparse
import logging
import os
from pathlib import Path

import folium
import geopandas as gpd
from dotenv import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load GeoParquet from S3 and render an interactive map."
    )
    parser.add_argument(
        "--s3-url",
        required=True,
        help="S3 URL to GeoParquet, e.g. s3://bucket/path/file.parquet",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="AWS profile name (defaults to AWS_PROFILE from .env/env)",
    )
    parser.add_argument(
        "--output",
        default="map.html",
        help="Output HTML file path for the map",
    )
    return parser.parse_args()


def build_map(gdf: gpd.GeoDataFrame) -> folium.Map:
    if gdf.empty:
        return folium.Map(location=[0, 0], zoom_start=2)

    gdf = gdf.to_crs(epsg=4326)
    # Ensure properties are JSON-serializable for Folium/Jinja.
    for col in gdf.columns:
        if col == "geometry":
            continue
        if gdf[col].dtype.kind == "M":
            gdf[col] = gdf[col].dt.strftime("%Y-%m-%dT%H:%M:%S")

    bounds = gdf.total_bounds
    center = [(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2]
    fmap = folium.Map(location=center, zoom_start=8, tiles="CartoDB positron")

    folium.GeoJson(
        gdf.__geo_interface__,
        name="vector-layer",
        tooltip=folium.GeoJsonTooltip(fields=list(gdf.columns.drop("geometry"))[:5]),
    ).add_to(fmap)

    fmap.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    folium.LayerControl().add_to(fmap)
    return fmap


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    load_dotenv()

    args = parse_args()
    profile = args.profile or os.getenv("AWS_PROFILE")
    storage_options = {"profile": profile} if profile else None

    logging.info("Reading GeoParquet from %s", args.s3_url)
    gdf = gpd.read_parquet(args.s3_url, storage_options=storage_options)
    fmap = build_map(gdf)

    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(output_path))
    logging.info("Map saved to %s", output_path)


if __name__ == "__main__":
    main()
