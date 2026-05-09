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
    help='Path to the input GeoParquet file.'
)
@click.option(
    '-o', '--output', 
    'output_file', 
    type=click.Path(dir_okay=False, path_type=Path), 
    help='Path to the output GeoJSON file. Defaults to the input path with a .geojson extension.'
)
def cli(input_file: Path, output_file: Path) -> None:
    """
    Converts a GeoParquet file to a GeoJSON file using Pyogrio.
    WARNING: GeoJSON is uncompressed text. The output file may be significantly 
    larger than the input GeoParquet file.
    """
    if output_file is None:
        output_file = input_file.with_suffix('.geojson')

    # Ensure parent directory exists for the output file
    output_file.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"Reading {input_file.name}...")
    
    try:
        # Read the GeoParquet file
        gdf = gpd.read_parquet(input_file)
        
        click.echo(f"Loaded {len(gdf)} features. Converting to GeoJSON...")
        click.secho(
            "Note: Depending on dataset size, this may take a moment and produce a very large file.", 
            fg="yellow"
        )
        
        # Write to GeoJSON using the Pyogrio engine
        gdf.to_file(output_file, driver="GeoJSON", engine="pyogrio")
        
        click.secho(f"Success! GeoJSON saved to: {output_file}", fg="green")
        
    except Exception as e:
        click.secho(f"Conversion failed: {e}", fg="red", err=True)
        sys.exit(1)

if __name__ == '__main__':
    cli()