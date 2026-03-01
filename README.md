# GeoTIFF to XYZ Tiles Converter for Marine Chartplotter

This project provides a robust Python script to process georeferenced marine charts in GeoTIFF format and generate raster image tiles. These tiles follow the standard **XYZ / Slippy Map** directory structure (`{z}/{x}/{y}.png`), which is widely used in web mapping and compatible with various embedded systems, including ESP32-based plotter projects.

## Features

* **Standard XYZ Structure**: Generates tiles in the `{z}/{x}/{y}.png` format.
* **Automatic Reprojection**: Handles reprojection to **EPSG:3857 (Web Mercator)** automatically.
* **Customizable Zoom Levels**: Specify the minimum (`--zmin`) and maximum (`--zmax`) zoom levels via command-line arguments.
* **High-Quality Resampling**: Uses **bilinear** resampling by default for better visual results on marine charts.
* **Standard Tile Size**: Generates standard 256x256 pixel tiles.

## Prerequisites

The script requires the **GDAL** library and its Python bindings.

### Installation

#### macOS (using Homebrew)
1. Install GDAL:
   ```bash
   brew install gdal
   ```
2. Install Python GDAL bindings (ensure they match your GDAL version):
   ```bash
   pip install gdal==$(gdal-config --version)
   ```

#### Ubuntu / Debian
1. Install GDAL development libraries and binaries:
   ```bash
   sudo apt-get update && sudo apt-get install -y libgdal-dev gdal-bin python3-gdal
   ```
2. Install Python GDAL bindings:
   ```bash
   pip install gdal==$(gdal-config --version)
   ```

## Usage

The script is callable from the command line and accepts the following arguments:

```bash
python3 process_chart.py <input_geotiff> <output_directory> --zmin <min_zoom> --zmax <max_zoom>
```

### Parameters:
* `input_geotiff`: Path to the source GeoTIFF file.
* `output_directory`: Path where the generated tiles will be stored.
* `--zmin`: The minimum zoom level to generate (default: 0).
* `--zmax`: The maximum zoom level to generate (default: 10).

### Example:
To generate tiles for zoom levels 0 through 5 from a chart named `marine_chart.tif` and save them in a folder called `tiles`:

```bash
python3 process_chart.py marine_chart.tif tiles --zmin 0 --zmax 5
```

## How it Works

The script leverages the `gdal2tiles` utility provided by GDAL. It:
1. Validates the input file and zoom levels.
2. Configures `gdal2tiles` to use the Mercator profile and XYZ tile scheme.
3. Sets the resampling method to bilinear.
4. Executes the tiling process, creating a directory structure like:
   ```
   tiles/
   ├── 0/
   │   └── 0/
   │       └── 0.png
   ├── 1/
   │   ├── 0/
   │   │   └── 0.png
   │   └── 1/
   │       └── 1.png
   └── ...
   ```
