# Vector Layers to S3 (GeoParquet)

This folder contains two small scripts:

- `upload.py`: Detects a vector file format (`.shp` + companions, `.geojson/.json`, or `.zip` with a shapefile), converts it to GeoParquet, and uploads it to S3.
- `show.py`: Reads a GeoParquet file from S3 and renders an interactive HTML map.

## Setup

Create and activate a virtual environment (recommended), then install minimal dependencies for the script you plan to run.

### upload.py dependencies

```bash
pip3 install geopandas pyarrow boto3 python-dotenv
```

### show.py dependencies

```bash
pip3 install geopandas pyarrow s3fs folium python-dotenv
```

## AWS authentication

Both scripts can use `AWS_PROFILE` from a local `.env` file in this folder (or set it in your shell).

Example `.env`:

```bash
AWS_PROFILE=your-profile-name
```

## Usage

### Upload a vector file to S3 as GeoParquet

```bash
python3 upload.py --input /path/to/data.zip --bucket your-bucket
```

Optional flags:

- `--key`: S3 object key (default: `<input-stem>.parquet`)
- `--profile`: AWS profile name (overrides `AWS_PROFILE`)
- `--output`: Local GeoParquet output path (if you want to keep a file)

### Show a GeoParquet file from S3 on a map

```bash
python3 show.py --s3-url s3://your-bucket/path/file.parquet --output map.html
```

Optional flags:

- `--profile`: AWS profile name (overrides `AWS_PROFILE`)
- `--output`: Output HTML file path (default: `map.html`)
