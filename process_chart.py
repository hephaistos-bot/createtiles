#!/usr/bin/env python3
"""
GeoTIFF to XYZ Tiles Converter
------------------------------
This script processes a GeoTIFF file and generates raster image tiles in the
standard XYZ / Slippy Map directory structure ({z}/{x}/{y}.png or {z}/{x}/{y}.jpg).
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
    python3 process_chart.py input_chart.tif output_tiles --zmin 0 --zmax 5 --tile-format jpg
"""

import argparse
import sys
import os
import struct
from osgeo import gdal, osr

# Enable GDAL exceptions to suppress FutureWarnings and for better error handling
gdal.UseExceptions()
osr.UseExceptions()

from osgeo_utils import gdal2tiles

def convert_to_rgb565(png_path, rgb565_path):
    """
    Converts a PNG tile to RGB565 raw format.
    Blends with white background if transparency is present.
    """
    ds = gdal.Open(png_path)
    if not ds:
        return False

    width = ds.RasterXSize
    height = ds.RasterYSize
    bands = ds.RasterCount

    r_band = ds.GetRasterBand(1).ReadRaster()
    g_band = ds.GetRasterBand(2).ReadRaster()
    b_band = ds.GetRasterBand(3).ReadRaster()
    a_band = None
    if bands == 4:
        a_band = ds.GetRasterBand(4).ReadRaster()

    ds = None # Close dataset

    # Buffer the entire tile to speed up writing
    rgb565_data = bytearray(width * height * 2)

    for i in range(width * height):
        r = r_band[i]
        g = g_band[i]
        b = b_band[i]

        if a_band is not None:
            alpha = a_band[i] / 255.0
            r = int(r * alpha + 255 * (1 - alpha))
            g = int(g * alpha + 255 * (1 - alpha))
            b = int(b * alpha + 255 * (1 - alpha))

        # Pack into RGB565 (5 bits Red, 6 bits Green, 5 bits Blue)
        # Big-Endian default: [RRRRRGGG] [GGGBBBBB]
        # To switch to Little-Endian, use '<H' instead of '>H'
        val = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

        # Manually pack Big-Endian for speed
        rgb565_data[i*2] = (val >> 8) & 0xFF
        rgb565_data[i*2 + 1] = val & 0xFF

    with open(rgb565_path, 'wb') as f:
        f.write(rgb565_data)

    return True

def process_geotiff(input_file, output_dir, zmin, zmax, tile_format):
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

    # Map the user-provided tile format to the corresponding GDAL driver name
    tile_driver = 'PNG'
    actual_format = tile_format
    if tile_format == 'rgb565':
        # We'll generate PNGs first then convert
        tile_driver = 'PNG'
    elif tile_format == 'jpg':
        # Check GDAL version for JPEG support in gdal2tiles
        # Native JPEG support in gdal2tiles was added in GDAL 3.9
        gdal_version = gdal.VersionInfo('RELEASE_NAME')
        try:
            version_tuple = tuple(map(int, gdal_version.split('.')[:2]))
            if version_tuple < (3, 9):
                print(f"Error: JPEG output requires GDAL 3.9 or newer. Current version is {gdal_version}.")
                sys.exit(1)
        except (ValueError, IndexError):
            # Fallback for unexpected version string formats
            print(f"Warning: Could not reliably parse GDAL version '{gdal_version}'. Attempting to proceed.")

        tile_driver = 'JPEG'

    options = {
        'profile': 'mercator',
        'resampling': 'bilinear',
        'zoom': f"{zmin}-{zmax}",
        'xyz': True,
        'tilesize': 256,
        'tiledriver': tile_driver,
        'quiet': False,
        'verbose': True
    }

    print(f"Starting tiling process for {input_file}...")
    print(f"Zoom levels: {zmin} to {zmax}")
    print(f"Output directory: {output_dir}")
    print(f"Resampling: bilinear")
    print(f"Format: {tile_driver} (XYZ structure)")

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

        if actual_format == 'rgb565':
            print("\nConverting tiles to RGB565...")
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    if file.endswith('.png'):
                        png_path = os.path.join(root, file)
                        rgb565_path = os.path.join(root, file.replace('.png', '.rgb565'))
                        if convert_to_rgb565(png_path, rgb565_path):
                            os.remove(png_path)
            print("Conversion to RGB565 completed.")

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
    parser.add_argument("--tile-format", choices=['png', 'jpg', 'rgb565'], default='png', help="Output tile format (default: png)")

    args = parser.parse_args()

    # Basic validation of zoom levels
    if args.zmin < 0 or args.zmax < args.zmin:
        print("Error: Invalid zoom levels. Ensure 0 <= zmin <= zmax.")
        sys.exit(1)

    process_geotiff(args.input, args.output, args.zmin, args.zmax, args.tile_format)

if __name__ == "__main__":
    main()
