# src/pipeline/tasks/prodes.py

import io
import zipfile
import numpy as np
import requests
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import box
from prefect import task, get_run_logger

from src.pipeline.utils.s3_utils import upload_bytes


PRODES_DOWNLOAD_URL = (
    "https://terrabrasilis.dpi.inpe.br/download/dataset/amazon-prodes/"
    "vector/yearly_deforestation_biome.zip"
)


def fetch_prodes_polygons(
    bbox: tuple,
    state_filter: str,
    year_start: int,
    year_end: int
) -> gpd.GeoDataFrame:
    """
    Download PRODES annual deforestation shapefile from TerraBrasilis.
    Filters to state and year range. bbox: (minx, miny, maxx, maxy) EPSG:4326.
    """
    response = requests.get(PRODES_DOWNLOAD_URL, timeout=300, stream=True)
    response.raise_for_status()

    zip_bytes = io.BytesIO(response.content)
    with zipfile.ZipFile(zip_bytes) as zf:
        shp_files = [f for f in zf.namelist() if f.endswith(".shp")]
        if not shp_files:
            raise ValueError("No shapefile found in PRODES zip download")

        with zf.open(shp_files[0]) as shp:
            gdf = gpd.read_file(shp)

    if gdf.empty:
        return gdf

    gdf = gdf.set_crs("EPSG:4326", allow_override=True)

    # filter by state
    if "state" in gdf.columns:
        gdf = gdf[gdf["state"] == state_filter]
    elif "uf" in gdf.columns:
        gdf = gdf[gdf["uf"] == state_filter]

    # filter by year
    if "year" in gdf.columns:
        gdf = gdf[(gdf["year"] >= year_start) & (gdf["year"] <= year_end)]

    # clip to AOI bbox
    aoi_box = box(*bbox)
    gdf = gdf[gdf.intersects(aoi_box)].copy()

    return gdf


def rasterise_prodes(
    prodes_gdf: gpd.GeoDataFrame,
    reference_transform,
    reference_shape: tuple,
    year: int
) -> np.ndarray:
    """
    Rasterise PRODES polygons for a given year to match a reference raster grid.
    Returns binary mask: 1 = deforested, 0 = not deforested.
    """
    if prodes_gdf.empty:
        return np.zeros(reference_shape, dtype=np.uint8)

    year_polygons = prodes_gdf[prodes_gdf["year"] == year]

    if year_polygons.empty:
        return np.zeros(reference_shape, dtype=np.uint8)

    mask = rasterize(
        shapes=[(geom, 1) for geom in year_polygons.geometry],
        out_shape=reference_shape,
        transform=reference_transform,
        fill=0,
        dtype=np.uint8
    )

    return mask


@task(retries=2, retry_delay_seconds=60)
def fetch_and_rasterise_prodes(
    run_id: str,
    reference_raster_path: str,
    config: dict
) -> dict:
    """
    Download PRODES polygons, rasterise per year, upload to S3.
    Returns dict of S3 keys per year.
    """
    logger = get_run_logger()
    prodes_config = config["prodes"]
    aoi_bounds = config["aoi"]["bounds"]
    bucket = config["s3"]["bucket"]

    logger.info("Downloading PRODES shapefile from TerraBrasilis")

    try:
        prodes_gdf = fetch_prodes_polygons(
            bbox=tuple(aoi_bounds),
            state_filter=prodes_config["state_filter"],
            year_start=2020,
            year_end=2023
        )
        logger.info(f"PRODES polygons downloaded: {len(prodes_gdf)} features")
    except Exception as e:
        # if PRODES download fails, log warning and use empty masks
        # pipeline continues - PRODES used for validation only, not core methodology
        logger.warning(f"PRODES download failed: {e} - using empty validation masks")
        prodes_gdf = gpd.GeoDataFrame()

    with rasterio.open(reference_raster_path) as ref:
        ref_transform = ref.transform
        ref_shape = (ref.height, ref.width)
        ref_profile = ref.profile.copy()

    s3_keys = {}
    for year in [2020, 2021, 2022, 2023]:
        mask = rasterise_prodes(prodes_gdf, ref_transform, ref_shape, year)
        s3_key = f"mato-grosso/runs/{run_id}/rasters/prodes_{year}.tif"

        ref_profile.update({
            "count": 1,
            "dtype": "uint8",
            "compress": "deflate",
            "driver": "GTiff"
        })

        buffer = io.BytesIO()
        with rasterio.open(buffer, "w", **ref_profile) as dst:
            dst.write(mask, 1)

        upload_bytes(buffer.getvalue(), bucket, s3_key)
        logger.info(f"PRODES {year} raster written to s3://{bucket}/{s3_key}")
        s3_keys[year] = s3_key

    return s3_keys