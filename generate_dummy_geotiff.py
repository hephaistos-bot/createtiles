import os
from osgeo import gdal, osr
import array
import sys

# Simple 3x5 pixel font for digits and some letters
# 15 bits: 3 cols x 5 rows (Top-Left to Bottom-Right)
PIXEL_FONT = {
    '0': 0x7B6F, '1': 0x2492, '2': 0x73E7, '3': 0x71C7, '4': 0x55F1,
    '5': 0x7C71, '6': 0x7C77, '7': 0x7124, '8': 0x7577, '9': 0x7571,
    'T': 0x7249, # 111, 010, 010, 010, 010
    'L': 0x4927, # 100, 100, 100, 100, 111
    'R': 0x757D, # 111, 101, 111, 110, 101
    'D': 0x656E  # 110, 101, 101, 101, 110
}

def draw_char(r_data, g_data, b_data, width, height, x_start, y_start, char, scale=2):
    """Draws a single character starting at (x_start, y_start)."""
    if char not in PIXEL_FONT:
        return
    bits = PIXEL_FONT[char]
    for row in range(5):
        for col in range(3):
            if (bits >> (14 - (row * 3 + col))) & 1:
                for dy in range(scale):
                    for dx in range(scale):
                        y, x = y_start + row * scale + dy, x_start + col * scale + dx
                        if 0 <= y < height and 0 <= x < width:
                            idx = y * width + x
                            r_data[idx], g_data[idx], b_data[idx] = 0, 0, 0

def draw_text(r_data, g_data, b_data, width, height, x_center, y_center, text, scale=2):
    """Draws text centered at (x_center, y_center)."""
    s_text = str(text)
    digit_w = 3 * scale
    spacing = 1 * scale
    total_w = len(s_text) * digit_w + (len(s_text) - 1) * spacing
    total_h = 5 * scale

    x_start = x_center - total_w // 2
    y_start = y_center - total_h // 2

    # White background square
    padding = scale * 2
    for y in range(y_start - padding, y_start + total_h + padding):
        for x in range(x_start - padding, x_start + total_w + padding):
            if 0 <= y < height and 0 <= x < width:
                idx = y * width + x
                r_data[idx], g_data[idx], b_data[idx] = 255, 255, 255

    curr_x = x_start
    for char in s_text:
        draw_char(r_data, g_data, b_data, width, height, curr_x, y_start, char, scale)
        curr_x += digit_w + spacing

def generate_dummy_geotiff(filename, width=512, height=512):
    """Generates a 3-band RGB GeoTIFF with patterns and orientation markers."""

    r_data = array.array('B', [0] * (width * height))
    g_data = array.array('B', [0] * (width * height))
    b_data = array.array('B', [0] * (width * height))

    for y in range(height):
        for x in range(width):
            idx = y * width + x

            # 1. Repeating patterns (smaller than 256x256)
            r_data[idx] = (y % 128) * 2
            g_data[idx] = (x % 128) * 2
            if ((x // 64) + (y // 64)) % 2 == 0:
                b_data[idx] = 200
            else:
                b_data[idx] = 50

            # 2. Global gradients
            r_data[idx] = min(255, r_data[idx] + int((y / height) * 50))
            g_data[idx] = min(255, g_data[idx] + int((x / width) * 50))

            # 3. Orientation markers (corners)
            marker_size = 20
            if y < marker_size:
                if x < marker_size: # TL
                    r_data[idx], g_data[idx], b_data[idx] = 255, 255, 255
                elif x >= width - marker_size: # TR
                    r_data[idx], g_data[idx], b_data[idx] = 255, 0, 0
            elif y >= height - marker_size:
                if x < marker_size: # BL
                    r_data[idx], g_data[idx], b_data[idx] = 0, 255, 0
                elif x >= width - marker_size: # BR
                    r_data[idx], g_data[idx], b_data[idx] = 0, 0, 255

    # 4. Large Letters T, L, R, D
    draw_text(r_data, g_data, b_data, width, height, width//2, 40, "T", scale=4)
    draw_text(r_data, g_data, b_data, width, height, 40, height//2, "L", scale=4)
    draw_text(r_data, g_data, b_data, width, height, width-40, height//2, "R", scale=4)
    draw_text(r_data, g_data, b_data, width, height, width//2, height-40, "D", scale=4)

    # 5. Sequential numbers in the middle of each 128x128 area
    num_x = (width + 127) // 128
    num_y = (height + 127) // 128
    for row in range(num_y):
        for col in range(num_x):
            seq_idx = row * num_x + col
            x_center = col * 128 + 64
            y_center = row * 128 + 64
            if x_center < width and y_center < height:
                draw_text(r_data, g_data, b_data, width, height, x_center, y_center, str(seq_idx), scale=3)

    driver = gdal.GetDriverByName('GTiff')
    if driver is None:
        print("GTiff driver not available.")
        return

    dataset = driver.Create(filename, width, height, 3, gdal.GDT_Byte)
    dataset.SetGeoTransform([0, 0.01, 0, 0, 0, -0.01])
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())

    for i, data in enumerate([r_data, g_data, b_data], 1):
        band = dataset.GetRasterBand(i)
        band.WriteRaster(0, 0, width, height, data.tobytes())
        if i == 1: band.SetColorInterpretation(gdal.GCI_RedBand)
        elif i == 2: band.SetColorInterpretation(gdal.GCI_GreenBand)
        elif i == 3: band.SetColorInterpretation(gdal.GCI_BlueBand)

    dataset.FlushCache()
    dataset = None
    print(f"Generated dummy 3-band GeoTIFF: {filename} ({width}x{height})")

if __name__ == "__main__":
    w, h = 512, 512
    output_file = "test_input.tif"
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
