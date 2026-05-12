import sys
from pathlib import Path
import click
from rio_cogeo.cogeo import cog_translate
from rio_cogeo.profiles import cog_profiles

@click.command()
@click.option(
    '-i', '--input', 
    'input_file', 
    required=True, 
    type=click.Path(exists=True, dir_okay=False, path_type=Path), 
    help='Path to the input GeoTIFF file.'
)
@click.option(
    '-o', '--output', 
    'output_file', 
    type=click.Path(dir_okay=False, path_type=Path), 
    help='Path to the output Cloud-Optimized GeoTIFF (COG). Defaults to input with _cog.tif suffix.'
)
def cli(input_file: Path, output_file: Path) -> None:
    """
    Converts a standard GeoTIFF to a Cloud-Optimized GeoTIFF (COG) using rio-cogeo.
    """
    if output_file is None:
        output_file = input_file.parent / f"{input_file.stem}_cog.tif"

    # Ensure parent directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"Reading {input_file.name}...")
    
    try:
        # Load the default DEFLATE profile for standard lossless compression
        output_profile = cog_profiles.get("deflate")
        
        # Configure standard COG optimization parameters
        output_profile.update(dict(BIGTIFF="IF_SAFER"))
        
        # Configure GDAL environment for threading and internal structures
        config = dict(
            GDAL_NUM_THREADS="ALL_CPUS",
            GDAL_TIFF_INTERNAL_MASK=True,
            GDAL_TIFF_OVR_BLOCKSIZE="128",
        )
        
        click.echo("Generating overviews and writing Cloud-Optimized GeoTIFF...")
        
        # Convert to COG
        cog_translate(
            str(input_file),
            str(output_file),
            output_profile,
            config=config,
            in_memory=False,    # Keeps memory low for large rasters
            quiet=False
        )
        
        click.secho(f"Success! COG saved to: {output_file}", fg="green")
        
    except Exception as e:
        click.secho(f"Conversion failed: {e}", fg="red", err=True)
        sys.exit(1)

if __name__ == '__main__':
    cli()