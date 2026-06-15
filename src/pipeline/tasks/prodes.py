# src/pipeline/tasks/prodes.py

import numpy as np
import requests
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from shapely.geometry import box
from prefect import task, get_run_logger

from src.pipeline.utils.s3_utils import upload_bytes


def fetch_prodes_polygons(
    wfs_url: str,
    layer: str,
    state_filter: str,
    year_start: int,
    year_end: int,
    bbox: tuple
) -> gpd.GeoDataFrame:
    """
    Fetch PRODES annual deforestation polygons from TerraBrasilis WFS API.
    bbox: (minx, miny, maxx, maxy) in EPSG:4326.
    Returns GeoDataFrame of deforestation polygons.
    """
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": layer,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "bbox": f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]},EPSG:4326",
        "CQL_FILTER": (
            f"state='{state_filter}' AND "
            f"year >= {year_start} AND year <= {year_end}"
        )
    }

    response = requests.get(wfs_url, params=params, timeout=120)
    response.raise_for_status()

    gdf = gpd.read_file(response.text)

    if gdf.empty:
        return gdf

    # clip to AOI bounds
    aoi_box = box(*bbox)
    gdf = gdf[gdf.intersects(aoi_box)].copy()
    gdf = gdf.set_crs("EPSG:4326", allow_override=True)

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
    Fetch PRODES polygons for the study period, rasterise per year,
    and upload to S3 as validation reference layers.
    Returns dict of S3 keys per year.
    """
    logger = get_run_logger()
    prodes_config = config["prodes"]
    aoi_bounds = config["aoi"]["bounds"]
    bucket = config["s3"]["bucket"]

    logger.info("Fetching PRODES deforestation polygons from TerraBrasilis")

    prodes_gdf = fetch_prodes_polygons(
        wfs_url=prodes_config["wfs_url"],
        layer=prodes_config["layer"],
        state_filter=prodes_config["state_filter"],
        year_start=2020,
        year_end=2023,
        bbox=tuple(aoi_bounds)
    )

    logger.info(f"PRODES polygons fetched: {len(prodes_gdf)} features")

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
            "compress": "deflate"
        })

        import io
        buffer = io.BytesIO()
        with rasterio.open(buffer, "w", **ref_profile) as dst:
            dst.write(mask, 1)

        upload_bytes(buffer.getvalue(), bucket, s3_key)
        s3_keys[year] = s3_key
        logger.info(f"PRODES {year} raster written to s3://{bucket}/{s3_key}")

    return s3_keys