# src/pipeline/utils/raster_utils.py

import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.crs import CRS


def write_cog(
    data: np.ndarray,
    profile: dict,
    output_path: str
):
    """
    Write a numpy array as a Cloud-Optimised GeoTIFF.
    Supports both local paths and s3:// paths via rasterio's S3 support.
    """
    profile.update({
        "driver": "GTiff",
        "dtype": "float32",
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
        "interleave": "band"
    })

    with rasterio.open(output_path, "w", **profile) as dst:
        if data.ndim == 2:
            dst.write(data.astype(np.float32), 1)
        else:
            for i, band in enumerate(data, 1):
                dst.write(band.astype(np.float32), i)


def reproject_raster(
    src_path: str,
    dst_path: str,
    dst_crs: str = "EPSG:32721"
):
    """
    Reproject a raster to a target CRS and write as COG.
    Used to convert GEE outputs (EPSG:4326) to UTM for area calculations.
    """
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, CRS.from_epsg(int(dst_crs.split(":")[1])),
            src.width, src.height, *src.bounds
        )
        profile = src.profile.copy()
        profile.update({
            "crs": dst_crs,
            "transform": transform,
            "width": width,
            "height": height,
            "driver": "GTiff",
            "compress": "deflate",
            "tiled": True,
            "blockxsize": 256,
            "blockysize": 256
        })

        with rasterio.open(dst_path, "w", **profile) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.bilinear
                )


def read_band(src_path: str, band: int = 1) -> tuple:
    """
    Read a single band from a raster file.
    Returns (array, profile, transform, crs).
    """
    with rasterio.open(src_path) as src:
        data = src.read(band)
        return data, src.profile.copy(), src.transform, src.crs


def pixel_area_ha(transform) -> float:
    """
    Calculate pixel area in hectares from a rasterio transform.
    Assumes transform is in metres (UTM). Do not use with geographic CRS.
    """
    pixel_width = abs(transform.a)
    pixel_height = abs(transform.e)
    return (pixel_width * pixel_height) / 10000