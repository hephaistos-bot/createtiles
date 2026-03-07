#!/usr/bin/env python3
import struct
import sys
import os
from osgeo import gdal, osr

# Enable GDAL exceptions
gdal.UseExceptions()
osr.UseExceptions()

def verify_rgb565(rgb565_path, output_path, width=256, height=256):
    """
    Converts an RGB565 raw file back to a GeoTIFF for verification.
    """
    if not os.path.exists(rgb565_path):
        print(f"Error: {rgb565_path} not found.")
        return

    with open(rgb565_path, 'rb') as f:
        data = f.read()

    expected_size = width * height * 2
    if len(data) != expected_size:
        print(f"Error: Unexpected file size. Expected {expected_size}, got {len(data)}")
        return

    r_band = bytearray(width * height)
    g_band = bytearray(width * height)
    b_band = bytearray(width * height)

    for i in range(width * height):
        # Read 16-bit Big-Endian value
        val = (data[i*2] << 8) | data[i*2+1]

        # Unpack RGB565
        r = (val >> 11) & 0x1F
        g = (val >> 5) & 0x3F
        b = val & 0x1F

        # Scale to 8-bit
        r_band[i] = (r * 255) // 31
        g_band[i] = (g * 255) // 63
        b_band[i] = (b * 255) // 31

    # Save as GeoTIFF using GDAL
    driver = gdal.GetDriverByName('GTiff')
    ds = driver.Create(output_path, width, height, 3, gdal.GDT_Byte)
    ds.GetRasterBand(1).WriteRaster(0, 0, width, height, bytes(r_band))
    ds.GetRasterBand(2).WriteRaster(0, 0, width, height, bytes(g_band))
    ds.GetRasterBand(3).WriteRaster(0, 0, width, height, bytes(b_band))

    # Set color interpretation
    ds.GetRasterBand(1).SetColorInterpretation(gdal.GCI_RedBand)
    ds.GetRasterBand(2).SetColorInterpretation(gdal.GCI_GreenBand)
    ds.GetRasterBand(3).SetColorInterpretation(gdal.GCI_BlueBand)

    ds.FlushCache()
    ds = None
    print(f"Verification GeoTIFF saved to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python verify_rgb565.py <input.rgb565> <output.tif>")
        sys.exit(1)

    verify_rgb565(sys.argv[1], sys.argv[2])
