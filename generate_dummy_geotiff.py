import os
from osgeo import gdal, osr
import array
import sys

def generate_dummy_geotiff(filename, width=512, height=512):
    """Generates a 3-band RGB GeoTIFF with patterns and orientation markers."""

    # Initialize arrays for R, G, B bands
    r_data = array.array('B', [0] * (width * height))
    g_data = array.array('B', [0] * (width * height))
    b_data = array.array('B', [0] * (width * height))

    for y in range(height):
        for x in range(width):
            idx = y * width + x

            # 1. Repeating patterns (smaller than 256x256)
            # Red: Repeating vertical gradient every 128px
            r_data[idx] = (y % 128) * 2

            # Green: Repeating horizontal gradient every 128px
            g_data[idx] = (x % 128) * 2

            # Blue: 64x64 checkerboard
            if ((x // 64) + (y // 64)) % 2 == 0:
                b_data[idx] = 200
            else:
                b_data[idx] = 50

            # 2. Global gradients (to distinguish tiles)
            # Add a slight global gradient to R and G
            r_data[idx] = min(255, r_data[idx] + int((y / height) * 50))
            g_data[idx] = min(255, g_data[idx] + int((x / width) * 50))

            # 3. Orientation markers (20x20 blocks in corners)
            marker_size = 20
            if y < marker_size:
                if x < marker_size:
                    # Top-Left: White
                    r_data[idx], g_data[idx], b_data[idx] = 255, 255, 255
                elif x >= width - marker_size:
                    # Top-Right: Red
                    r_data[idx], g_data[idx], b_data[idx] = 255, 0, 0
            elif y >= height - marker_size:
                if x < marker_size:
                    # Bottom-Left: Green
                    r_data[idx], g_data[idx], b_data[idx] = 0, 255, 0
                elif x >= width - marker_size:
                    # Bottom-Right: Blue
                    r_data[idx], g_data[idx], b_data[idx] = 0, 0, 255

            # 4. Simple "T" for Top and "L" for Left (crude drawing)
            # "T" at (width//2, 30)
            if 30 <= y <= 35 and width//2 - 10 <= x <= width//2 + 10:
                r_data[idx], g_data[idx], b_data[idx] = 255, 255, 0 # Yellow
            if 35 < y <= 55 and width//2 - 2 <= x <= width//2 + 2:
                r_data[idx], g_data[idx], b_data[idx] = 255, 255, 0 # Yellow

            # "L" at (30, height//2)
            if height//2 - 10 <= y <= height//2 + 10 and 30 <= x <= 35:
                r_data[idx], g_data[idx], b_data[idx] = 255, 255, 0 # Yellow
            if height//2 + 8 <= y <= height//2 + 10 and 35 < x <= 50:
                r_data[idx], g_data[idx], b_data[idx] = 255, 255, 0 # Yellow

    driver = gdal.GetDriverByName('GTiff')
    if driver is None:
        print("GTiff driver not available.")
        return

    # Create dataset with 3 bands
    dataset = driver.Create(filename, width, height, 3, gdal.GDT_Byte)

    # Set a dummy geotransform: [top left x, w-e pixel resolution, rotation, top left y, rotation, n-s pixel resolution]
    dataset.SetGeoTransform([0, 0.01, 0, 0, 0, -0.01])

    # Set the projection to EPSG:4326 (WGS84)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())

    # Write data to the bands
    for i, data in enumerate([r_data, g_data, b_data], 1):
        band = dataset.GetRasterBand(i)
        band.WriteRaster(0, 0, width, height, data.tobytes())

        # Set color interpretation
        if i == 1: band.SetColorInterpretation(gdal.GCI_RedBand)
        elif i == 2: band.SetColorInterpretation(gdal.GCI_GreenBand)
        elif i == 3: band.SetColorInterpretation(gdal.GCI_BlueBand)

    # Clean up
    dataset.FlushCache()
    dataset = None
    print(f"Generated dummy 3-band GeoTIFF: {filename} ({width}x{height})")
    print("Orientation markers: Top-Left=White, Top-Right=Red, Bottom-Left=Green, Bottom-Right=Blue")
    print("Patterns: 128px gradients (R/G) and 64px checkerboard (B)")

if __name__ == "__main__":
    # Default values
    w, h = 512, 512
    output_file = "test_input.tif"

    # Simple argument handling
    if len(sys.argv) >= 3:
        try:
            w = int(sys.argv[1])
            h = int(sys.argv[2])
        except ValueError:
            print("Usage: python generate_dummy_geotiff.py [width] [height] [filename]")
            sys.exit(1)

    if len(sys.argv) >= 4:
        output_file = sys.argv[3]

    generate_dummy_geotiff(output_file, w, h)
