# src/pipeline/tasks/prodes.py

import io
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from shapely.geometry import box
from prefect import task, get_run_logger

from src.pipeline.utils.s3_utils import upload_bytes

PRODES_SHP_PATH = (
    "raw_data/prodes/yearly_deforestation_biome_amazonia_v20260608/"
    "yearly_deforestation_biome_amazonia_v20260608.shp"
)


def load_prodes_polygons(
    bbox: tuple,
    state_filter: str,
    year_start: int,
    year_end: int
) -> gpd.GeoDataFrame:
    """
    Load PRODES annual deforestation polygons from local shapefile.
    Filters to state, year range, and AOI bbox.
    bbox: (minx, miny, maxx, maxy) in EPSG:4326.
    """
    gdf = gpd.read_file(PRODES_SHP_PATH)

    # filter by state
    gdf = gdf[gdf["state"] == state_filter]

    # filter by year range
    gdf = gdf[(gdf["year"] >= year_start) & (gdf["year"] <= year_end)]

    # reproject to EPSG:4326 for consistency with raster grid
    gdf = gdf.to_crs("EPSG:4326")

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
    Load PRODES polygons from local shapefile, rasterise per year,
    upload to S3 as validation reference layers.
    Returns dict of S3 keys per year.
    """
    logger = get_run_logger()
    prodes_config = config["prodes"]
    aoi_bounds = config["aoi"]["bounds"]
    bucket = config["s3"]["bucket"]

    logger.info("Loading PRODES polygons from local shapefile")

    try:
        prodes_gdf = load_prodes_polygons(
            bbox=tuple(aoi_bounds),
            state_filter=prodes_config["state_filter"],
            year_start=2020,
            year_end=2023
        )
        logger.info(f"PRODES polygons loaded: {len(prodes_gdf)} features")
    except Exception as e:
        logger.warning(f"PRODES load failed: {e} - using empty validation masks")
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