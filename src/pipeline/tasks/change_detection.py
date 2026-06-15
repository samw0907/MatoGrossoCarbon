# src/pipeline/tasks/change_detection.py

import numpy as np
import rasterio
from rasterio.features import shapes
from scipy.ndimage import label
from shapely.geometry import shape
import geopandas as gpd
from prefect import task, get_run_logger


def calculate_dnbr(nbr_t1: np.ndarray, nbr_t2: np.ndarray) -> np.ndarray:
    """Calculate dNBR: NBR at t1 minus NBR at t2. Positive = loss."""
    return nbr_t1 - nbr_t2


def apply_threshold(dnbr: np.ndarray, threshold: float) -> np.ndarray:
    """Apply dNBR threshold to produce binary deforestation mask."""
    return (dnbr > threshold).astype(np.uint8)


def apply_forest_mask(deforestation: np.ndarray, forest_t1: np.ndarray) -> np.ndarray:
    """Only retain deforestation detections within forest at baseline epoch."""
    return (deforestation & (forest_t1 == 1)).astype(np.uint8)


def apply_mapbiomas_filter(
    deforestation: np.ndarray,
    forest_t1: np.ndarray,
    forest_t2: np.ndarray
) -> np.ndarray:
    """
    Retain only pixels that were forest at t1 and non-forest at t2.
    This is the MapBiomas transitions filter.
    """
    transition = ((forest_t1 == 1) & (forest_t2 == 0)).astype(np.uint8)
    return (deforestation & transition).astype(np.uint8)


def delineate_patches(
    deforestation_mask: np.ndarray,
    transform,
    crs,
    min_area_ha: float = 1.0
) -> gpd.GeoDataFrame:
    """
    Label connected components in deforestation mask, vectorise to patches,
    filter by minimum area. Returns GeoDataFrame of deforestation patches.
    """
    labelled, num_features = label(deforestation_mask)

    if num_features == 0:
        return gpd.GeoDataFrame(columns=["patch_id", "area_ha", "geometry"])

    # vectorise patches
    patch_shapes = list(shapes(labelled.astype(np.int32), transform=transform))
    patches = []
    for geom, patch_id in patch_shapes:
        if patch_id == 0:
            continue
        polygon = shape(geom)
        # area in ha: convert from degrees to metres using approximate factor
        area_m2 = polygon.area * (111320 ** 2)
        area_ha = area_m2 / 10000
        if area_ha >= min_area_ha:
            patches.append({
                "patch_id": int(patch_id),
                "area_ha": round(area_ha, 4),
                "geometry": polygon
            })

    if not patches:
        return gpd.GeoDataFrame(columns=["patch_id", "area_ha", "geometry"])

    return gpd.GeoDataFrame(patches, crs=crs)


def calibrate_threshold(
    dnbr: np.ndarray,
    prodes_mask: np.ndarray,
    forest_t1: np.ndarray,
    sweep_min: float = -0.05,
    sweep_max: float = -0.25,
    steps: int = 20
) -> tuple:
    """
    Sweep dNBR threshold against PRODES reference mask.
    Returns (optimal_threshold, f1_score) that maximises F1.
    """
    thresholds = np.linspace(sweep_min, sweep_max, steps)
    best_threshold = sweep_min
    best_f1 = 0.0

    forest_pixels = forest_t1 == 1

    for thresh in thresholds:
        predicted = (dnbr > abs(thresh)) & forest_pixels
        reference = prodes_mask == 1

        tp = np.sum(predicted & reference)
        fp = np.sum(predicted & ~reference)
        fn = np.sum(~predicted & reference)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        if f1 > best_f1:
            best_f1 = f1
            best_threshold = thresh

    return best_threshold, best_f1


@task(retries=2, retry_delay_seconds=30)
def run_change_detection(
    transition: str,
    s3_raster_prefix: str,
    config: dict
) -> dict:
    """
    Placeholder task for change detection - reads rasters from S3,
    runs dNBR, threshold calibration, patch delineation.
    Implemented fully in Phase 3 once rasters are in S3.
    """
    logger = get_run_logger()
    logger.info(f"Change detection for transition {transition} - awaiting Phase 3 implementation")
    return {"transition": transition, "status": "pending"}