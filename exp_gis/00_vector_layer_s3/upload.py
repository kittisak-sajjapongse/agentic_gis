#!/usr/bin/env python3
import argparse
import logging
import os
import tempfile
import zipfile
from pathlib import Path

from typing import Optional

import boto3
import geopandas as gpd
from dotenv import load_dotenv


def find_single_shapefile(search_dir: Path) -> Path:
    shapefiles = sorted(search_dir.rglob("*.shp"))
    if not shapefiles:
        raise FileNotFoundError(f"No .shp found in {search_dir}")
    if len(shapefiles) > 1:
        names = ", ".join(p.name for p in shapefiles)
        raise ValueError(f"Multiple .shp found in {search_dir}: {names}")
    return shapefiles[0]


def resolve_input(input_path: Path):
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    suffix = input_path.suffix.lower()
    if input_path.is_dir():
        shp = find_single_shapefile(input_path)
        return shp, None
    if suffix == ".zip":
        temp_dir = tempfile.TemporaryDirectory()
        with zipfile.ZipFile(input_path) as zf:
            zf.extractall(temp_dir.name)
        shp = find_single_shapefile(Path(temp_dir.name))
        return shp, temp_dir
    if suffix in {".shp", ".geojson", ".json"}:
        return input_path, None

    raise ValueError(f"Unsupported input format: {input_path}")


def write_geoparquet(gdf: gpd.GeoDataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(output_path, index=False, engine="pyarrow")


def upload_to_s3(local_path: Path, bucket: str, key: str, profile: Optional[str]) -> None:
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    client = session.client("s3")
    client.upload_file(str(local_path), bucket, key)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert vector data to GeoParquet and upload to S3."
    )
    parser.add_argument("--input", required=True, help="Path to .shp, .geojson, or .zip")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument(
        "--key",
        default=None,
        help="S3 object key (defaults to <input-stem>.parquet)",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="AWS profile name (defaults to AWS_PROFILE from .env/env)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional local output path for GeoParquet",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    load_dotenv()

    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    profile = args.profile or os.getenv("AWS_PROFILE")

    temp_dir = None
    temp_output = None
    try:
        read_path, temp_dir = resolve_input(input_path)
        logging.info("Reading vector data from %s", read_path)
        gdf = gpd.read_file(read_path)

        if args.output:
            output_path = Path(args.output).expanduser().resolve()
        else:
            temp_output = tempfile.TemporaryDirectory()
            output_path = Path(temp_output.name) / f"{read_path.stem}.parquet"

        write_geoparquet(gdf, output_path)
        key = args.key or f"{read_path.stem}.parquet"
        logging.info("Uploading %s to s3://%s/%s", output_path, args.bucket, key)
        upload_to_s3(output_path, args.bucket, key, profile)
        logging.info("Upload complete.")
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
        if temp_output is not None:
            temp_output.cleanup()


if __name__ == "__main__":
    main()
