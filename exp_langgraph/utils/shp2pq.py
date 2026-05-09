import sys
from pathlib import Path
import click
import geopandas as gpd

@click.command()
@click.option(
    '-i', '--input', 
    'input_file', 
    required=True, 
    type=click.Path(exists=True, dir_okay=False, path_type=Path), 
    help='Path to the input Shapefile.'
)
@click.option(
    '-o', '--output', 
    'output_file', 
    type=click.Path(dir_okay=False, path_type=Path), 
    help='Path to the output GeoParquet file. Defaults to the input path with a .parquet extension.'
)
def cli(input_file: Path, output_file: Path) -> None:
    """
    Converts a Shapefile to GeoParquet using the optimized Pyogrio engine.
    """
    # Fallback to swapping the extension if no output is provided
    if output_file is None:
        output_file = input_file.with_suffix('.parquet')

    click.echo(f"Reading {input_file.name} using Pyogrio engine...")
    
    try:
        # Use pyogrio for fast C-level bindings instead of fiona
        gdf = gpd.read_file(input_file, engine="pyogrio")
        
        click.echo(f"Loaded {len(gdf)} features. Converting to GeoParquet...")
        
        # Write to GeoParquet specification v1.0.0
        gdf.to_parquet(
            output_file, 
            compression='snappy', 
            index=False,               
            geometry_encoding='WKB',   
            schema_version='1.0.0'     
        )
        
        click.secho(f"Success! GeoParquet saved to: {output_file}", fg="green")
        
    except Exception as e:
        click.secho(f"Conversion failed: {e}", fg="red", err=True)
        sys.exit(1)

if __name__ == '__main__':
    cli()