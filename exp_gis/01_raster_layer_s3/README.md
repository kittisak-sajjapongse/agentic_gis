# Raster Layers to S3 (GeoTIFF/COG)

This folder contains two small scripts:

- `upload.py`: Converts a GeoTIFF (`.tif/.tiff`) to a Cloud Optimized GeoTIFF (COG) and uploads it to S3.
- `show.py`: Reads a GeoTIFF from S3 and renders an interactive HTML map.

## Setup

Create and activate a virtual environment (recommended), then install minimal dependencies for the script you plan to run.

### upload.py dependencies

```bash
pip3 install boto3 rio-cogeo rasterio python-dotenv
```

### show.py dependencies

```bash
pip3 install boto3 rasterio folium numpy python-dotenv
```

## AWS authentication

Both scripts can use `AWS_PROFILE` from a local `.env` file in this folder (or set it in your shell).

Example `.env`:

```bash
AWS_PROFILE=your-profile-name
```

## Usage

### Upload a GeoTIFF to S3 as a COG

```bash
python3 upload.py --input /path/to/image.tif --bucket your-bucket
```

Optional flags:

- `--key`: S3 object key (default: input file name)
- `--profile`: AWS profile name (overrides `AWS_PROFILE`)

### Show a GeoTIFF from S3 on a map

```bash
python3 show.py --s3-url s3://your-bucket/path/file.tif --output map.html
```

Optional flags:

- `--profile`: AWS profile name (overrides `AWS_PROFILE`)
- `--output`: Output HTML file path (default: `map.html`)
- `--max-size`: Maximum pixel size for the largest raster dimension
