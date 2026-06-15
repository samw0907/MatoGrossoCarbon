# tests/unit/test_raster_utils.py

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
import tempfile
import os

from src.pipeline.utils.raster_utils import (
    write_cog,
    read_band,
    pixel_area_ha
)


def make_test_raster(path: str, data: np.ndarray, crs: str = "EPSG:32721"):
    """Helper: write a small test raster to a temp file."""
    transform = from_bounds(0, 0, 1000, 1000, data.shape[1], data.shape[0])
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "width": data.shape[1],
        "height": data.shape[0],
        "count": 1,
        "crs": crs,
        "transform": transform
    }
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data.astype(np.float32), 1)
    return transform


def test_write_cog_creates_file():
    data = np.random.rand(64, 64).astype(np.float32)
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
        path = f.name
    try:
        transform = from_bounds(0, 0, 1000, 1000, 64, 64)
        profile = {
            "width": 64,
            "height": 64,
            "count": 1,
            "crs": "EPSG:32721",
            "transform": transform
        }
        write_cog(data, profile, path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
    finally:
        os.unlink(path)


def test_write_cog_readable():
    data = np.ones((64, 64), dtype=np.float32) * 42.0
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
        path = f.name
    try:
        transform = from_bounds(0, 0, 1000, 1000, 64, 64)
        profile = {
            "width": 64,
            "height": 64,
            "count": 1,
            "crs": "EPSG:32721",
            "transform": transform
        }
        write_cog(data, profile, path)
        read_data, _, _, _ = read_band(path)
        np.testing.assert_array_almost_equal(read_data, data)
    finally:
        os.unlink(path)


def test_read_band_returns_correct_shape():
    data = np.random.rand(32, 32).astype(np.float32)
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as f:
        path = f.name
    try:
        make_test_raster(path, data)
        result, profile, transform, crs = read_band(path)
        assert result.shape == (32, 32)
        assert "width" in profile
        assert transform is not None
    finally:
        os.unlink(path)


def test_pixel_area_ha():
    # 30m x 30m pixel = 900 m2 = 0.09 ha
    transform = from_bounds(0, 0, 300, 300, 10, 10)
    area = pixel_area_ha(transform)
    assert area == pytest.approx(0.09, rel=1e-3)