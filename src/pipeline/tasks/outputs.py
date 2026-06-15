# src/pipeline/tasks/outputs.py

import json
import geopandas as gpd
from datetime import datetime
from prefect import task, get_run_logger

from src.pipeline.utils.s3_utils import upload_bytes


@task(retries=2, retry_delay_seconds=30)
def write_carbon_summary(
    summary: dict,
    transition: str,
    run_id: str,
    config: dict
) -> str:
    """Write carbon summary JSON to S3. Returns S3 key."""
    logger = get_run_logger()
    bucket = config["s3"]["bucket"]
    s3_key = f"mato-grosso/runs/{run_id}/reports/carbon_summary_{transition}.json"

    summary["run_id"] = run_id
    summary["generated_at"] = datetime.utcnow().isoformat()

    data = json.dumps(summary, indent=2).encode("utf-8")
    upload_bytes(data, bucket, s3_key)

    logger.info(f"Carbon summary written to s3://{bucket}/{s3_key}")
    return s3_key


@task(retries=2, retry_delay_seconds=30)
def write_patch_geojson(
    patch_gdf: gpd.GeoDataFrame,
    transition: str,
    run_id: str,
    config: dict
) -> str:
    """Write deforestation patch GeoJSON to S3. Returns S3 key."""
    logger = get_run_logger()
    bucket = config["s3"]["bucket"]
    s3_key = f"mato-grosso/runs/{run_id}/vectors/deforestation_patches_{transition}.geojson"

    geojson_str = patch_gdf.to_json()
    upload_bytes(geojson_str.encode("utf-8"), bucket, s3_key)

    logger.info(f"Patch GeoJSON written to s3://{bucket}/{s3_key}")
    return s3_key


@task(retries=2, retry_delay_seconds=30)
def write_run_manifest(
    run_id: str,
    s3_keys: list,
    summaries: list,
    config: dict,
    task_statuses: dict
) -> str:
    """Write run manifest JSON to S3. Returns S3 key."""
    logger = get_run_logger()
    bucket = config["s3"]["bucket"]
    s3_key = f"mato-grosso/runs/{run_id}/reports/run_manifest.json"

    manifest = {
        "run_id": run_id,
        "generated_at": datetime.utcnow().isoformat(),
        "study_area": "Mato Grosso, Brazil",
        "epochs": config["epochs"],
        "transitions": config["transitions"],
        "methodology": "IPCC Tier 1 / VCS-aligned",
        "gedi_product": "L4B_v2.1",
        "mapbiomas_collection": 10,
        "s3_outputs": s3_keys,
        "carbon_summaries": summaries,
        "task_statuses": task_statuses
    }

    data = json.dumps(manifest, indent=2).encode("utf-8")
    upload_bytes(data, bucket, s3_key)

    logger.info(f"Run manifest written to s3://{bucket}/{s3_key}")
    return s3_key