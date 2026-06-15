# src/pipeline/tasks/change_detection.py

import numpy as np
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

    patch_shapes = list(shapes(labelled.astype(np.int32), transform=transform))
    patches = []
    for geom, patch_id in patch_shapes:
        if patch_id == 0:
            continue
        polygon = shape(geom)
        # approximate area conversion from degrees to hectares
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
        f1 = (
            (2 * precision * recall / (precision + recall))
            if (precision + recall) > 0 else 0.0
        )

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
    Run full change detection for a transition period.
    Reads Sentinel-2 NBR composites and MapBiomas forest masks from local cache,
    runs dNBR calculation, threshold calibration against PRODES,
    applies MapBiomas transition filter, delineates patches.
    Returns dict with patches GeoDataFrame and detection metadata.
    """
    logger = get_run_logger()
    logger.info(f"Running change detection for transition {transition}")

    epoch_t1 = transition.split("-")[0]
    epoch_t2 = "-".join(transition.split("-")[1:])

    # derive run_id from s3_raster_prefix: mato-grosso/runs/{run_id}/rasters
    parts = s3_raster_prefix.split("/")
    run_id = parts[2] if len(parts) >= 3 else "unknown"
    local_dir = f"outputs/rasters/{run_id}"

    from src.pipeline.utils.raster_utils import read_band

    composite_t1_path = f"{local_dir}/sentinel2_composite_{epoch_t1}.tif"
    composite_t2_path = f"{local_dir}/sentinel2_composite_{epoch_t2}.tif"
    forest_t1_path = f"{local_dir}/mapbiomas_forest_{epoch_t1}.tif"
    forest_t2_path = f"{local_dir}/mapbiomas_forest_{epoch_t2}.tif"

    # NBR is band 8 in composite band order: B2,B4,B5,B8,B11,B12,NDVI,NBR,NDMI,NDRE,EVI
    nbr_t1, profile, transform, crs = read_band(composite_t1_path, band=8)
    nbr_t2, _, _, _ = read_band(composite_t2_path, band=8)
    forest_t1, _, _, _ = read_band(forest_t1_path, band=1)
    forest_t2, _, _, _ = read_band(forest_t2_path, band=1)

    # use end epoch year as PRODES validation reference year
    prodes_year = int(epoch_t2[:4])
    prodes_path = f"{local_dir}/prodes_{prodes_year}.tif"
    prodes_mask, _, _, _ = read_band(prodes_path, band=1)

    # calculate dNBR
    dnbr = calculate_dnbr(nbr_t1, nbr_t2)

    # calibrate threshold against PRODES
    cd_config = config["change_detection"]
    optimal_threshold, f1_score = calibrate_threshold(
        dnbr=dnbr,
        prodes_mask=prodes_mask,
        forest_t1=(forest_t1 == 1).astype(np.uint8),
        sweep_min=cd_config["dnbr_threshold_sweep_min"],
        sweep_max=cd_config["dnbr_threshold_sweep_max"]
    )
    logger.info(f"Optimal dNBR threshold: {optimal_threshold:.3f} (F1: {f1_score:.3f})")

    # apply threshold
    deforestation = apply_threshold(dnbr, threshold=abs(optimal_threshold))

    # apply forest baseline mask
    deforestation = apply_forest_mask(
        deforestation,
        (forest_t1 == 1).astype(np.uint8)
    )

    # apply MapBiomas transition filter
    deforestation = apply_mapbiomas_filter(
        deforestation,
        (forest_t1 == 1).astype(np.uint8),
        (forest_t2 == 1).astype(np.uint8)
    )

    # delineate patches
    patch_gdf = delineate_patches(
        deforestation_mask=deforestation,
        transform=transform,
        crs=crs,
        min_area_ha=cd_config["min_patch_area_ha"]
    )

    logger.info(f"Transition {transition}: {len(patch_gdf)} patches detected")

    return {
        "transition": transition,
        "patches": patch_gdf,
        "dnbr_threshold": optimal_threshold,
        "f1_score": f1_score,
        "patch_count": len(patch_gdf),
        "status": "completed"
    }