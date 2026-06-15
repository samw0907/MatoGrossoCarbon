# src/pipeline/flows.py

import os
import yaml
from datetime import datetime
import ee
from prefect import flow, get_run_logger

from src.pipeline.utils.gee_utils import initialise_gee, get_aoi_geometry
from src.pipeline.utils.s3_utils import download_file
from src.pipeline.tasks.ingestion import (
    build_sentinel2_composite,
    export_composite_to_gcs,
    export_gedi_to_gcs,
    export_mapbiomas_to_gcs,
    transfer_gcs_to_s3
)
from src.pipeline.tasks.change_detection import run_change_detection
from src.pipeline.tasks.biomass import run_biomass_extraction
from src.pipeline.tasks.outputs import (
    write_carbon_summary,
    write_patch_geojson,
    write_run_manifest
)
from src.pipeline.tasks.prodes import fetch_and_rasterise_prodes


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

    for epoch in epochs:
        composite = build_sentinel2_composite(epoch, aoi, config)
        export_composite_to_gcs(composite, aoi, run_id, config)

    export_gedi_to_gcs(aoi, run_id, config)
    export_mapbiomas_to_gcs(aoi, run_id, config)

    s3_keys = transfer_gcs_to_s3(run_id, config)

    logger.info(f"Ingestion flow complete | {len(s3_keys)} files in S3")
    return s3_keys


@flow(name="carbon-flow", log_prints=True)
def carbon_flow(
    run_id: str,
    config: dict
):
    """
    Carbon flow: downloads rasters from S3, runs change detection,
    extracts biomass, calculates CO2e, writes outputs.
    """
    logger = get_run_logger()
    logger.info(f"Starting carbon flow | run_id: {run_id}")

    bucket = config["s3"]["bucket"]
    transitions = config["transitions"]
    local_raster_dir = f"outputs/rasters/{run_id}"
    os.makedirs(local_raster_dir, exist_ok=True)

    # download rasters from S3 to local cache
    logger.info("Downloading rasters from S3")
    s3_prefix = f"mato-grosso/runs/{run_id}/rasters"

    gedi_local = f"{local_raster_dir}/gedi_l4b_agbd.tif"
    download_file(bucket, f"{s3_prefix}/gedi_l4b_agbd.tif", gedi_local)

    for epoch in config["epochs"]:
        download_file(
            bucket,
            f"{s3_prefix}/sentinel2_composite_{epoch}.tif",
            f"{local_raster_dir}/sentinel2_composite_{epoch}.tif"
        )
        download_file(
            bucket,
            f"{s3_prefix}/mapbiomas_forest_{epoch}.tif",
            f"{local_raster_dir}/mapbiomas_forest_{epoch}.tif"
        )

    # fetch and rasterise PRODES validation reference
    reference_raster = f"{local_raster_dir}/sentinel2_composite_2020.tif"
    prodes_s3_keys = fetch_and_rasterise_prodes(run_id, reference_raster, config)

    for year in [2020, 2021, 2022, 2023]:
        download_file(
            bucket,
            f"{s3_prefix}/prodes_{year}.tif",
            f"{local_raster_dir}/prodes_{year}.tif"
        )

    # run change detection and carbon calculation per transition
    all_summaries = []
    all_s3_keys = []
    task_statuses = {}

    for transition in transitions:
        epoch_t1, epoch_t2 = transition.split("-")[0], transition.split("-")[1]

        try:
            result = run_change_detection(
                transition=transition,
                s3_raster_prefix=s3_prefix,
                config=config
            )

            patch_gdf = result.get("patches")
            if patch_gdf is not None and len(patch_gdf) > 0:
                biomass_result = run_biomass_extraction(
                    transition=transition,
                    patch_gdf=patch_gdf,
                    gedi_path=gedi_local,
                    reference_raster_path=reference_raster,
                    config=config
                )

                summary = biomass_result["summary"]
                enriched_gdf = biomass_result["patches"]

                geojson_key = write_patch_geojson(enriched_gdf, transition, run_id, config)
                summary_key = write_carbon_summary(summary, transition, run_id, config)

                all_summaries.append(summary)
                all_s3_keys.extend([geojson_key, summary_key])
                task_statuses[transition] = "completed"
            else:
                logger.warning(f"No deforestation patches found for {transition}")
                task_statuses[transition] = "no_patches"

        except Exception as e:
            logger.error(f"Carbon flow failed for {transition}: {e}")
            task_statuses[transition] = f"failed: {str(e)}"

    manifest_key = write_run_manifest(
        run_id=run_id,
        s3_keys=all_s3_keys,
        summaries=all_summaries,
        config=config,
        task_statuses=task_statuses
    )

    logger.info(f"Carbon flow complete | run_id: {run_id}")
    return {"run_id": run_id, "manifest": manifest_key, "summaries": all_summaries}