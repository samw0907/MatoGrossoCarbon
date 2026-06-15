# src/pipeline/flows.py

from datetime import datetime
import ee
from prefect import flow, get_run_logger

from src.pipeline.utils.gee_utils import initialise_gee, get_aoi_geometry
from src.pipeline.tasks.ingestion import (
    build_sentinel2_composite,
    export_composite_to_gcs,
    export_gedi_to_gcs,
    export_mapbiomas_to_gcs,
    transfer_gcs_to_s3
)


@flow(name="ingestion-flow", log_prints=True)
def ingestion_flow(
    service_account_email: str,
    key_file: str,
    project: str,
    epochs: list,
    config: dict,
    run_id: str
):
    """Ingestion flow: GEE composites exported to GCS then transferred to S3."""
    logger = get_run_logger()
    logger.info(f"Starting ingestion flow | run_id: {run_id}")

    initialise_gee(service_account_email, key_file, project)
    aoi = get_aoi_geometry(config["aoi_path"])

    # build and export Sentinel-2 composites sequentially
    for epoch in epochs:
        composite = build_sentinel2_composite(epoch, aoi, config)
        export_composite_to_gcs(composite, aoi, run_id, config)

    # export GEDI and MapBiomas
    export_gedi_to_gcs(aoi, run_id, config)
    export_mapbiomas_to_gcs(aoi, run_id, config)

    # transfer all GCS outputs to S3 and clean up GCS
    s3_keys = transfer_gcs_to_s3(run_id, config)

    logger.info(f"Ingestion flow complete | {len(s3_keys)} files in S3")
    return s3_keys


@flow(name="carbon-flow", log_prints=True)
def carbon_flow(transitions: list):
    """Carbon flow: change detection, biomass extraction, CO2e calculation (Phase 3)."""
    logger = get_run_logger()
    logger.info("Starting carbon flow - Phase 3 implementation pending")