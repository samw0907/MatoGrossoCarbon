# src/pipeline/tasks/biomass.py

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
import geopandas as gpd
from prefect import task, get_run_logger

from src.pipeline.utils.carbon_utils import (
    co2e_from_patch,
    co2e_lower_90,
    co2e_upper_90,
    summarise_patches
)


def resample_gedi_to_grid(
    gedi_path: str,
    reference_path: str
) -> tuple:
    """
    Resample GEDI L4B (1km) to match the Sentinel-2 grid (30m).
    Returns (agbd_array, se_array) resampled to reference grid.
    """
    with rasterio.open(reference_path) as ref:
        ref_transform = ref.transform
        ref_crs = ref.crs
        ref_shape = (ref.height, ref.width)

    with rasterio.open(gedi_path) as gedi:
        agbd = np.zeros(ref_shape, dtype=np.float32)
        se = np.zeros(ref_shape, dtype=np.float32)

        reproject(
            source=rasterio.band(gedi, 1),
            destination=agbd,
            src_transform=gedi.transform,
            src_crs=gedi.crs,
            dst_transform=ref_transform,
            dst_crs=ref_crs,
            resampling=Resampling.bilinear
        )

        reproject(
            source=rasterio.band(gedi, 2),
            destination=se,
            src_transform=gedi.transform,
            src_crs=gedi.crs,
            dst_transform=ref_transform,
            dst_crs=ref_crs,
            resampling=Resampling.bilinear
        )

    return agbd, se


def extract_patch_biomass(
    patch_gdf: gpd.GeoDataFrame,
    agbd: np.ndarray,
    se: np.ndarray,
    transform
) -> gpd.GeoDataFrame:
    """
    Extract zonal mean AGBD and SE for each deforestation patch.
    Adds agbd_mean, agbd_se, co2e_mg, co2e_lower_90, co2e_upper_90 columns.
    """
    from rasterio.features import geometry_mask

    agbd_means = []
    agbd_ses = []
    co2e_values = []
    co2e_lowers = []
    co2e_uppers = []

    for _, row in patch_gdf.iterrows():
        mask = geometry_mask(
            [row.geometry],
            transform=transform,
            invert=True,
            out_shape=agbd.shape
        )

        patch_agbd = agbd[mask]
        patch_se = se[mask]

        # filter nodata (0 or negative values)
        valid = patch_agbd > 0
        if valid.sum() == 0:
            agbd_mean = 0.0
            agbd_se_mean = 0.0
        else:
            agbd_mean = float(np.mean(patch_agbd[valid]))
            agbd_se_mean = float(np.mean(patch_se[valid]))

        area_ha = row["area_ha"]
        co2e = co2e_from_patch(agbd_mean, area_ha)
        co2e_low = co2e_lower_90(agbd_mean, agbd_se_mean, area_ha)
        co2e_high = co2e_upper_90(agbd_mean, agbd_se_mean, area_ha)

        agbd_means.append(round(agbd_mean, 2))
        agbd_ses.append(round(agbd_se_mean, 2))
        co2e_values.append(round(co2e, 2))
        co2e_lowers.append(round(co2e_low, 2))
        co2e_uppers.append(round(co2e_high, 2))

    patch_gdf = patch_gdf.copy()
    patch_gdf["agbd_mean_mg_ha"] = agbd_means
    patch_gdf["agbd_se_mg_ha"] = agbd_ses
    patch_gdf["co2e_mg"] = co2e_values
    patch_gdf["co2e_lower_90"] = co2e_lowers
    patch_gdf["co2e_upper_90"] = co2e_uppers

    return patch_gdf


@task(retries=2, retry_delay_seconds=30)
def run_biomass_extraction(
    transition: str,
    patch_gdf: gpd.GeoDataFrame,
    gedi_path: str,
    reference_raster_path: str,
    config: dict
) -> dict:
    """
    Extract biomass per patch and calculate carbon loss.
    Returns summary dict and enriched GeoDataFrame.
    """
    logger = get_run_logger()
    logger.info(f"Running biomass extraction for transition {transition}")

    agbd, se = resample_gedi_to_grid(gedi_path, reference_raster_path)

    with rasterio.open(reference_raster_path) as ref:
        transform = ref.transform

    enriched_gdf = extract_patch_biomass(patch_gdf, agbd, se, transform)

    patches_list = enriched_gdf[
        ["area_ha", "agbd_mean_mg_ha", "co2e_mg", "co2e_lower_90", "co2e_upper_90"]
    ].rename(columns={
        "agbd_mean_mg_ha": "agbd_mean",
        "co2e_lower_90": "co2e_lower_90",
        "co2e_upper_90": "co2e_upper_90"
    }).to_dict("records")

    summary = summarise_patches(patches_list)
    summary["epoch_transition"] = transition

    logger.info(
        f"Transition {transition}: {summary.get('patch_count', 0)} patches, "
        f"{summary.get('total_co2e_mg', 0):.0f} Mg CO2e"
    )

    return {"summary": summary, "patches": enriched_gdf}