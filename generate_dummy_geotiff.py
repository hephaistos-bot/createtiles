import os
from osgeo import gdal, osr
import array
import sys

# Enable GDAL exceptions to suppress FutureWarnings and for better error handling
gdal.UseExceptions()
osr.UseExceptions()

def decimal_to_dm(value, is_lat):
    """Converts decimal degrees to Degrees and Decimal Minutes format."""
    if is_lat:
        hemisphere = "N" if value >= 0 else "S"
        degrees_width = 2
    else:
        hemisphere = "E" if value >= 0 else "W"
        degrees_width = 3

    abs_value = abs(value)
    degrees = int(abs_value)
    minutes = (abs_value - degrees) * 60

    return f"{degrees:0{degrees_width}d}° {minutes:06.3f}' {hemisphere}"

# Standard 3x5 pixel font represented by 15-bit integers
PIXEL_FONT = {
    '0': 0b111101101101111,
    '1': 0b010010010010010,
    '2': 0b111001111100111,
    '3': 0b111001111001111,
    '4': 0b101101111001001,
    '5': 0b111100111001111,
    '6': 0b111100111101111,
    '7': 0b111001001001001,
    '8': 0b111101111101111,
    '9': 0b111101111001001,
    'T': 0b111010010010010,
    'L': 0b100100100100111,
    'R': 0b110101110101101,
    'D': 0b110101101101110
}

def draw_char(r_data, g_data, b_data, width, height, x_start, y_start, char, scale=2):
    """Draws a single character starting at (x_start, y_start)."""
    if char not in PIXEL_FONT:
        return
    bits = PIXEL_FONT[char]
    for row in range(5):
        for col in range(3):
            # Bit extraction: bit 14 is top-left, bit 0 is bottom-right
            if (bits >> (14 - (row * 3 + col))) & 1:
                # Draw a scaled pixel (Black)
                for dy in range(scale):
                    for dx in range(scale):
                        y, x = y_start + row * scale + dy, x_start + col * scale + dx
                        if 0 <= y < height and 0 <= x < width:
                            idx = y * width + x
                            r_data[idx], g_data[idx], b_data[idx] = 0, 0, 0

def draw_text(r_data, g_data, b_data, width, height, x_center, y_center, text, scale=4):
    """Draws text centered at (x_center, y_center)."""
    s_text = str(text)
    digit_w = 3 * scale
    spacing = 1 * scale
    total_w = len(s_text) * digit_w + (len(s_text) - 1) * spacing
    total_h = 5 * scale

    x_start = int(x_center - total_w / 2)
    y_start = int(y_center - total_h / 2)

    # White background square with extra padding for visibility
    padding = scale * 2
    for y in range(y_start - padding, y_start + total_h + padding):
        for x in range(x_start - padding, x_start + total_w + padding):
            if 0 <= y < height and 0 <= x < width:
                idx = y * width + x
                r_data[idx], g_data[idx], b_data[idx] = 255, 255, 255

    # Draw characters in Black
    curr_x = x_start
    for char in s_text:
        draw_char(r_data, g_data, b_data, width, height, curr_x, y_start, char, scale)
        curr_x += digit_w + spacing

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
            r_data[idx] = min(255, r_data[idx] + int((y / height) * 50))
            g_data[idx] = min(255, g_data[idx] + int((x / width) * 50))

            # 3. Orientation markers (20x20 blocks in corners)
            marker_size = 20
            if y < marker_size:
                if x < marker_size: # Top-Left: White
                    r_data[idx], g_data[idx], b_data[idx] = 255, 255, 255
                elif x >= width - marker_size: # Top-Right: Red
                    r_data[idx], g_data[idx], b_data[idx] = 255, 0, 0
            elif y >= height - marker_size:
                if x < marker_size: # Bottom-Left: Green
                    r_data[idx], g_data[idx], b_data[idx] = 0, 255, 0
                elif x >= width - marker_size: # Bottom-Right: Blue
                    r_data[idx], g_data[idx], b_data[idx] = 0, 0, 255

    # 4. Large Orientation Letters (T, L, R, D)
    draw_text(r_data, g_data, b_data, width, height, width // 2, 60, "T", scale=10)
    draw_text(r_data, g_data, b_data, width, height, 60, height // 2, "L", scale=10)
    draw_text(r_data, g_data, b_data, width, height, width - 60, height // 2, "R", scale=10)
    draw_text(r_data, g_data, b_data, width, height, width // 2, height - 60, "D", scale=10)

    # 5. Sequential numbers in the middle of each 128x128 pattern area
    num_x = (width + 127) // 128
    num_y = (height + 127) // 128
    for row in range(num_y):
        for col in range(num_x):
            seq_idx = row * num_x + col
            x_center = col * 128 + 64
            y_center = row * 128 + 64
            if x_center < width and y_center < height:
                draw_text(r_data, g_data, b_data, width, height, x_center, y_center, str(seq_idx), scale=6)

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

    # Robustly retrieve coordinates from the generated dataset
    gt = dataset.GetGeoTransform()
    ds_w = dataset.RasterXSize
    ds_h = dataset.RasterYSize

    corners = [
        ("Top-Left", 0, 0),
        ("Bottom-Right", ds_w, ds_h)
    ]

    corner_reports = []
    for label, px, py in corners:
        lon = gt[0] + px * gt[1] + py * gt[2]
        lat = gt[3] + px * gt[4] + py * gt[5]
        dm_format = f"{decimal_to_dm(lat, True)}, {decimal_to_dm(lon, False)}"
        decimal_format = f"Lat: {lat:.4f}, Lon: {lon:.4f}"
        corner_reports.append(f"{label:13}: {dm_format} ({decimal_format})")

    dataset = None

    print(f"Generated dummy 3-band GeoTIFF: {filename} ({width}x{height})")
    print("Orientation markers and sequential numbers added with improved readability.")

    print("\nCorner GPS Coordinates:")
    for report in corner_reports:
        print(report)

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
