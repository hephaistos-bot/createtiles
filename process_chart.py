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
    pip install gdal==$(gdal-config --version) Pillow

Installation (macOS via Homebrew):
    brew install gdal
    pip install gdal==$(gdal-config --version) Pillow

Example Usage:
    python3 process_chart.py input_chart.tif output_tiles --zmin 0 --zmax 5 --tile-format jpg
"""

import argparse
import sys
import os
import struct
from osgeo import gdal, osr
from PIL import Image

# Enable GDAL exceptions to suppress FutureWarnings and for better error handling
gdal.UseExceptions()
osr.UseExceptions()

from osgeo_utils import gdal2tiles

import numpy as np

# Configuration constants
JPEG_QUALITY = 60

def convert_to_rgb565(png_path, rgb565_path):
    """
    Fast conversion of a PNG tile to LVGL 9 compatible RGB565 binary.
    Includes the LVGL 9 12-byte header and uses Little-Endian for ESP32.
    """
    ds = gdal.Open(png_path)
    if not ds:
        return False

    width = ds.RasterXSize
    height = ds.RasterYSize
    bands = ds.RasterCount
    
    # Read all bands at once into a numpy array: shape (bands, height, width)
    data = ds.ReadAsArray()
    ds = None # Close dataset

    r = data[0].astype(np.float32)
    g = data[1].astype(np.float32)
    b = data[2].astype(np.float32)

    # Handle Alpha blending with white background vectorially
    if bands == 4:
        alpha = data[3].astype(np.float32) / 255.0
        r = (r * alpha + 255 * (1 - alpha))
        g = (g * alpha + 255 * (1 - alpha))
        b = (b * alpha + 255 * (1 - alpha))

    # Convert back to integers
    r = r.astype(np.uint16)
    g = g.astype(np.uint16)
    b = b.astype(np.uint16)

    # Pack into RGB565 bitwise
    # 5 bits Red, 6 bits Green, 5 bits Blue
    rgb565_matrix = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

    # LVGL v9 Image Header (12 bytes)
    # Struct format: 
    # uint8_t magic (0x19 for v9)
    # uint8_t cf (0x12 for LV_COLOR_FORMAT_RGB565)
    # uint16_t flags (0 for standard uncompressed)
    # uint16_t w (width)
    # uint16_t h (height)
    # uint16_t stride (width * 2 for RGB565)
    # uint16_t reserved (0)
    # '<' ensures Little-Endian packing
    lv_header = struct.pack('<BBHHHhh', 
                            0x19,       # Magic
                            0x12,       # Color format RGB565
                            0,          # Flags
                            width,      # Width
                            height,     # Height
                            width * 2,  # Stride in bytes
                            0)          # Reserved

    with open(rgb565_path, 'wb') as f:
        f.write(lv_header)
        # Write the pixel data in Little-Endian format
        f.write(rgb565_matrix.astype('<u2').tobytes())

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
    # We use PNG as an intermediate format for rgb565 and jpg to have better control
    # over the final output (transparency blending, subsampling, etc.)
    tile_driver = 'PNG'
    actual_format = tile_format

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
    print(f"Target Format: {actual_format} (XYZ structure)")

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

        if actual_format in ['rgb565', 'jpg']:
            print(f"\nConverting/Optimizing tiles to {actual_format}...")
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    if file.endswith('.png'):
                        png_path = os.path.join(root, file)

                        if actual_format == 'rgb565':
                            rgb565_path = os.path.join(root, file.replace('.png', '.rgb565'))
                            if convert_to_rgb565(png_path, rgb565_path):
                                os.remove(png_path)

                        elif actual_format == 'jpg':
                            jpg_path = os.path.join(root, file.replace('.png', '.jpg'))
                            with Image.open(png_path) as img:
                                # Convert to pure RGB (remove alpha if present)
                                if img.mode in ("RGBA", "P"):
                                    # Create white background to replace transparency
                                    background = Image.new("RGB", img.size, (255, 255, 255))
                                    if img.mode == "RGBA":
                                        background.paste(img, mask=img.split()[3])
                                    else:
                                        background.paste(img)
                                    img = background

                                # OPTIMIZED SAVE FOR ESP32
                                img.save(jpg_path, 'JPEG',
                                         quality=JPEG_QUALITY, # Controlled by constant
                                         optimize=True,        # Optimizes Huffman table
                                         progressive=False,    # MANDATORY: Baseline mode for S3 RAM
                                         subsampling=2)        # MANDATORY: Chroma Subsampling 4:2:0

                            os.remove(png_path)

            print(f"Conversion to {actual_format} completed.")

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
