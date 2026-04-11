#!/usr/bin/env python3
import argparse
import logging
import os
from pathlib import Path
from typing import Optional

import boto3
from dotenv import load_dotenv
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles
from rasterio.io import MemoryFile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload a GeoTIFF (.tif/.tiff) file to S3."
    )
    parser.add_argument("--input", required=True, help="Path to .tif or .tiff")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument(
        "--key",
        default=None,
        help="S3 object key (defaults to the input file name)",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="AWS profile name (defaults to AWS_PROFILE from .env/env)",
    )
    return parser.parse_args()


def upload_cog_to_s3(local_path: Path, bucket: str, key: str, profile: Optional[str]) -> None:
    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    client = session.client("s3")
    dst_profile = cog_profiles.get("deflate")
    with MemoryFile() as mem_dst:
        cog_translate(
            str(local_path),
            mem_dst.name,
            dst_profile,
            in_memory=True,
            quiet=True,
        )
        mem_dst.seek(0)
        client.upload_fileobj(mem_dst, bucket, key)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    load_dotenv()

    args = parse_args()
    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input not found: {input_path}")

    if input_path.suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError("Only .tif or .tiff files are supported.")

    profile = args.profile or os.getenv("AWS_PROFILE")
    key = args.key or input_path.name
    logging.info("Converting %s to COG and uploading to s3://%s/%s", input_path, args.bucket, key)
    upload_cog_to_s3(input_path, args.bucket, key, profile)
    logging.info("Upload complete.")


if __name__ == "__main__":
    main()
