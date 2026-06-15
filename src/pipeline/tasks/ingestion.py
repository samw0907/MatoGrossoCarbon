# src/pipeline/tasks/ingestion.py

import ee
import time
from prefect import task, get_run_logger

from src.pipeline.utils.gee_utils import get_aoi_geometry, mask_s2_scl
from src.pipeline.utils.gcs_utils import copy_gcs_to_s3


@task(retries=2, retry_delay_seconds=30)
def build_sentinel2_composite(epoch: str, aoi: ee.Geometry, config: dict) -> dict:
    """Build a Sentinel-2 dry season median composite for a given epoch."""
    logger = get_run_logger()
    s2_config = config["sentinel2"]

    start_date = f"{epoch}-{s2_config['composite_start_month']:02d}-01"
    end_date = f"{epoch}-{s2_config['composite_end_month']:02d}-30"

    logger.info(f"Building S2 composite for {epoch}: {start_date} to {end_date}")

    collection = (
        ee.ImageCollection(s2_config["collection"])
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .map(mask_s2_scl)
    )

    scene_count = collection.size().getInfo()
    logger.info(f"Epoch {epoch}: {scene_count} scenes after cloud masking")

    composite = collection.median().select(s2_config["bands"])

    ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
    nbr = composite.normalizedDifference(["B8", "B12"]).rename("NBR")
    ndmi = composite.normalizedDifference(["B8", "B11"]).rename("NDMI")
    ndre = composite.normalizedDifference(["B8", "B5"]).rename("NDRE")
    evi = composite.expression(
        "2.5 * ((B8 - B4) / (B8 + 6 * B4 - 7.5 * B2 + 1))",
        {"B8": composite.select("B8"), "B4": composite.select("B4"), "B2": composite.select("B2")}
    ).rename("EVI")

    composite_with_indices = composite.addBands([ndvi, nbr, ndmi, ndre, evi])

    return {
        "epoch": epoch,
        "image": composite_with_indices,
        "scene_count": scene_count
    }


def _poll_gee_task(gee_task, description: str, logger):
    """Poll a GEE batch task until completion. Raises on failure."""
    status = gee_task.status()
    while status["state"] in ["READY", "RUNNING"]:
        logger.info(f"{description}: {status['state']} - waiting 30s")
        time.sleep(30)
        status = gee_task.status()

    if status["state"] != "COMPLETED":
        raise RuntimeError(f"GEE task failed for {description}: {status}")

    logger.info(f"{description}: COMPLETED")


@task(retries=2, retry_delay_seconds=60)
def export_composite_to_gcs(
    composite_result: dict,
    aoi: ee.Geometry,
    run_id: str,
    config: dict
) -> str:
    """Export a Sentinel-2 composite to GCS. Returns GCS blob name."""
    logger = get_run_logger()
    epoch = composite_result["epoch"]
    image = composite_result["image"]
    gcs_bucket = config["gcs"]["bucket"]
    filename = f"sentinel2_composite_{epoch}"
    gcs_path = f"runs/{run_id}/{filename}"

    logger.info(f"Exporting {filename} to gs://{gcs_bucket}/{gcs_path}.tif")

    gee_task = ee.batch.Export.image.toCloudStorage(
        image=image.toFloat(),
        description=filename,
        bucket=gcs_bucket,
        fileNamePrefix=gcs_path,
        region=aoi,
        scale=30,
        crs="EPSG:4326",
        maxPixels=1e10,
        fileFormat="GeoTIFF"
    )
    gee_task.start()
    _poll_gee_task(gee_task, filename, logger)

    return gcs_path


@task(retries=2, retry_delay_seconds=60)
def export_gedi_to_gcs(aoi: ee.Geometry, run_id: str, config: dict) -> str:
    """Export GEDI L4B AGBD and SE bands to GCS."""
    logger = get_run_logger()
    gedi_config = config["gedi"]
    gcs_bucket = config["gcs"]["bucket"]
    filename = "gedi_l4b_agbd"
    gcs_path = f"runs/{run_id}/{filename}"

    logger.info(f"Loading GEDI L4B v2.1 and exporting to GCS")
    gedi = ee.Image(gedi_config["asset"]).select(
        [gedi_config["agbd_band"], gedi_config["se_band"]]
    ).clip(aoi)

    gee_task = ee.batch.Export.image.toCloudStorage(
        image=gedi.toFloat(),
        description=filename,
        bucket=gcs_bucket,
        fileNamePrefix=gcs_path,
        region=aoi,
        scale=1000,
        crs="EPSG:4326",
        maxPixels=1e10,
        fileFormat="GeoTIFF"
    )
    gee_task.start()
    _poll_gee_task(gee_task, filename, logger)

    return gcs_path


@task(retries=2, retry_delay_seconds=60)
def export_mapbiomas_to_gcs(aoi: ee.Geometry, run_id: str, config: dict) -> list:
    """Export MapBiomas forest masks to GCS for each epoch."""
    logger = get_run_logger()
    mb_config = config["mapbiomas"]
    gcs_bucket = config["gcs"]["bucket"]
    epochs = config["epochs"]

    logger.info("Loading MapBiomas Collection 10")
    mapbiomas = ee.Image(mb_config["asset"])

    gcs_paths = []
    for epoch in epochs:
        band_name = f"classification_{epoch}"
        lulc = mapbiomas.select(band_name)

        forest_mask = lulc.remap(
            mb_config["forest_classes"],
            [1] * len(mb_config["forest_classes"]),
            0
        ).rename(f"forest_{epoch}")

        filename = f"mapbiomas_forest_{epoch}"
        gcs_path = f"runs/{run_id}/{filename}"

        gee_task = ee.batch.Export.image.toCloudStorage(
            image=forest_mask.toFloat(),
            description=filename,
            bucket=gcs_bucket,
            fileNamePrefix=gcs_path,
            region=aoi,
            scale=30,
            crs="EPSG:4326",
            maxPixels=1e10,
            fileFormat="GeoTIFF"
        )
        gee_task.start()
        _poll_gee_task(gee_task, filename, logger)
        gcs_paths.append(gcs_path)

    return gcs_paths


@task(retries=2, retry_delay_seconds=30)
def transfer_gcs_to_s3(run_id: str, config: dict) -> list:
    """Copy all exported files from GCS run prefix to S3 and delete from GCS."""
    logger = get_run_logger()
    gcs_prefix = f"runs/{run_id}/"
    s3_prefix = f"mato-grosso/runs/{run_id}/rasters"

    logger.info(f"Transferring GCS gs://{config['gcs']['bucket']}/{gcs_prefix} to S3")

    s3_keys = copy_gcs_to_s3(
        key_file=config["gee"]["key_file"],
        gcs_bucket=config["gcs"]["bucket"],
        gcs_prefix=gcs_prefix,
        s3_bucket=config["s3"]["bucket"],
        s3_prefix=s3_prefix,
        delete_after=True
    )

    logger.info(f"Transfer complete: {len(s3_keys)} files in S3")
    return s3_keys