#!/usr/bin/env python3
"""
GeoTIFF to XYZ Tiles Converter
------------------------------
This script processes a GeoTIFF file and generates raster image tiles in the
standard XYZ / Slippy Map directory structure ({z}/{x}/{y}.png).
It automatically handles reprojection to EPSG:3857 (Web Mercator) if necessary.

Dependencies:
- GDAL (with Python bindings)

Installation (Ubuntu/Debian):
    sudo apt-get update && sudo apt-get install -y libgdal-dev gdal-bin python3-gdal
    pip install gdal==$(gdal-config --version)

Installation (macOS via Homebrew):
    brew install gdal
    pip install gdal==$(gdal-config --version)

Example Usage:
    python3 process_chart.py input_chart.tif output_tiles --zmin 0 --zmax 5
"""

import argparse
import sys
import os
from osgeo import gdal, osr

# Enable GDAL exceptions to suppress FutureWarnings and for better error handling
gdal.UseExceptions()
osr.UseExceptions()

from osgeo_utils import gdal2tiles

def process_geotiff(input_file, output_dir, zmin, zmax):
    """
    Processes the GeoTIFF and generates tiles using gdal2tiles.
    """
    # Ensure input file exists
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.")
        sys.exit(1)

    # Prepare gdal2tiles options
    # We use the Mercator profile (EPSG:3857) which is standard for web maps
    # We force XYZ tile numbering as requested.
    # Resampling is set to 'bilinear'.
    options = {
        'profile': 'mercator',
        'resampling': 'bilinear',
        'zoom': f"{zmin}-{zmax}",
        'xyz': True,
        'tilesize': 256,
        'tiledriver': 'PNG',
        'quiet': False,
        'verbose': True
    }

    print(f"Starting tiling process for {input_file}...")
    print(f"Zoom levels: {zmin} to {zmax}")
    print(f"Output directory: {output_dir}")
    print(f"Resampling: bilinear")
    print(f"Format: PNG (XYZ structure)")

    try:
        # In newer GDAL versions, we can use the GDAL2Tiles class
        # or call the main function with a list of arguments.
        # Since 'process' method is not directly available in some versions,
        # we construct the argument list for gdal2tiles.

        argv = ['gdal2tiles.py']

        # Add options to argv
        argv.extend(['--profile', options['profile']])
        argv.extend(['--resampling', options['resampling']])
        argv.extend(['--zoom', options['zoom']])
        if options['xyz']:
            argv.append('--xyz')
        argv.extend(['--tilesize', str(options['tilesize'])])
        argv.extend(['--tiledriver', options['tiledriver']])
        argv.extend(['--webviewer', 'none']) # We don't need the HTML viewer for ESP32

        argv.append(input_file)
        argv.append(output_dir)

        # Call gdal2tiles.main which handles the processing
        # We don't use --verbose here because it can trigger a bug in some GDAL versions
        # when generating overview tiles (log logging a tuple as a string).
        gdal2tiles.main(argv)

        print("\nTiling process completed successfully.")

    except Exception as e:
        print(f"\nAn error occurred during processing: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Convert GeoTIFF to XYZ map tiles.")

    parser.add_argument("input", help="Path to the input GeoTIFF file")
    parser.add_argument("output", help="Directory where tiles will be saved")
    parser.add_argument("--zmin", type=int, default=0, help="Minimum zoom level (default: 0)")
    parser.add_argument("--zmax", type=int, default=10, help="Maximum zoom level (default: 10)")

    args = parser.parse_args()

    # Basic validation of zoom levels
    if args.zmin < 0 or args.zmax < args.zmin:
        print("Error: Invalid zoom levels. Ensure 0 <= zmin <= zmax.")
        sys.exit(1)

    process_geotiff(args.input, args.output, args.zmin, args.zmax)

if __name__ == "__main__":
    main()
