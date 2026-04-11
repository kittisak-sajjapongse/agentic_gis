#!/usr/bin/env python3
import argparse
import logging
import os
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

import boto3
import folium
import numpy as np
import rasterio
from dotenv import load_dotenv
from rasterio.enums import Resampling
from rasterio.session import AWSSession
from rasterio.warp import transform_bounds


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load GeoTIFF from S3 and render an interactive map."
    )
    parser.add_argument(
        "--s3-url",
        required=True,
        help="S3 URL to GeoTIFF, e.g. s3://bucket/path/file.tif",
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
    parser.add_argument(
        "--max-size",
        type=int,
        default=2048,
        help="Maximum pixel size for the largest raster dimension",
    )
    return parser.parse_args()


def scale_to_uint8(array: np.ndarray) -> np.ndarray:
    min_val = np.nanmin(array)
    max_val = np.nanmax(array)
    if not np.isfinite(min_val) or not np.isfinite(max_val) or max_val == min_val:
        return np.zeros_like(array, dtype=np.uint8)
    scaled = (array - min_val) / (max_val - min_val)
    return (scaled * 255).astype(np.uint8)


def read_raster(
    s3_url: str,
    profile: Optional[str],
    max_size: int,
) -> Tuple[np.ndarray, Tuple[float, float, float, float]]:
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    aws_session = AWSSession(session)
    parsed = urlparse(s3_url)
    bucket = parsed.netloc

    # Rasterio/GDAL doesn't always resolve S3 bucket regions like s3fs does,
    # so we set the endpoint explicitly to avoid PermanentRedirect errors.
    region = session.region_name
    if not region:
        client = session.client("s3")
        location = client.get_bucket_location(Bucket=bucket).get("LocationConstraint")
        region = location or "us-east-1"
    endpoint = f"s3.{region}.amazonaws.com"

    with rasterio.Env(
        aws_session=aws_session,
        AWS_REGION=region,
        AWS_S3_ENDPOINT=endpoint,
    ):
        with rasterio.open(s3_url) as src:
            scale = min(1.0, max_size / max(src.width, src.height))
            out_width = max(1, int(src.width * scale))
            out_height = max(1, int(src.height * scale))
            data = src.read(
                out_shape=(src.count, out_height, out_width),
                resampling=Resampling.bilinear,
                masked=True,
            )
            data = data.filled(np.nan)

            if src.crs:
                bounds = transform_bounds(src.crs, "EPSG:4326", *src.bounds)
            else:
                bounds = src.bounds

    return data, bounds


def build_map(rgb: np.ndarray, bounds: Tuple[float, float, float, float]) -> folium.Map:
    west, south, east, north = bounds
    center = [(south + north) / 2, (west + east) / 2]
    fmap = folium.Map(location=center, zoom_start=8, tiles="CartoDB positron")

    folium.raster_layers.ImageOverlay(
        image=rgb,
        bounds=[[south, west], [north, east]],
        opacity=0.75,
        name="raster-layer",
    ).add_to(fmap)

    fmap.fit_bounds([[south, west], [north, east]])
    folium.LayerControl().add_to(fmap)
    return fmap


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    load_dotenv()

    args = parse_args()
    profile = args.profile or os.getenv("AWS_PROFILE")

    logging.info("Reading raster from %s", args.s3_url)
    data, bounds = read_raster(args.s3_url, profile, args.max_size)

    if data.shape[0] >= 3:
        rgb = np.stack(
            [scale_to_uint8(data[0]), scale_to_uint8(data[1]), scale_to_uint8(data[2])],
            axis=-1,
        )
    else:
        gray = scale_to_uint8(data[0])
        rgb = np.stack([gray, gray, gray], axis=-1)

    fmap = build_map(rgb, bounds)
    output_path = Path(args.output).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(output_path))
    logging.info("Map saved to %s", output_path)


if __name__ == "__main__":
    main()
