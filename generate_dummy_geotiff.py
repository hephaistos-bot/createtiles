import os
from osgeo import gdal, osr
import array

def generate_dummy_geotiff(filename, width=512, height=512):
    # Create some dummy data using array module instead of numpy
    data = array.array('B', [i % 256 for i in range(width * height)])

    driver = gdal.GetDriverByName('GTiff')
    dataset = driver.Create(filename, width, height, 1, gdal.GDT_Byte)

    # Set a dummy geotransform: [top left x, w-e pixel resolution, rotation, top left y, rotation, n-s pixel resolution]
    dataset.SetGeoTransform([0, 0.01, 0, 0, 0, -0.01])

    # Set the projection to EPSG:4326 (WGS84)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    dataset.SetProjection(srs.ExportToWkt())

    # Write data to the band
    band = dataset.GetRasterBand(1)
    # band.WriteArray is for numpy, use WriteRaster for raw bytes
    band.WriteRaster(0, 0, width, height, data.tobytes())

    # Clean up
    dataset.FlushCache()
    dataset = None
    print(f"Generated dummy GeoTIFF: {filename}")

if __name__ == "__main__":
    generate_dummy_geotiff("test_input.tif")
