# src/pipeline/flows.py

import ee
from prefect import flow, task, get_run_logger
from prefect.tasks import task_input_hash
from datetime import timedelta


@task(retries=2, retry_delay_seconds=30, cache_key_fn=task_input_hash, cache_expiration=timedelta(hours=24))
def initialise_gee(service_account_email: str, key_file: str, project: str):
    """Authenticate and initialise the GEE session."""
    logger = get_run_logger()
    credentials = ee.ServiceAccountCredentials(email=service_account_email, key_file=key_file)
    ee.Initialize(credentials, project=project)
    logger.info(f"GEE initialised for project: {project}")
    return True


@task(retries=2, retry_delay_seconds=30)
def placeholder_ingestion(epoch: str):
    """Placeholder for Sentinel-2 ingestion task (Phase 2)."""
    logger = get_run_logger()
    logger.info(f"Ingestion task for epoch {epoch} - not yet implemented")
    return {"epoch": epoch, "status": "placeholder"}


@task(retries=2, retry_delay_seconds=30)
def placeholder_carbon(transition: str):
    """Placeholder for carbon calculation task (Phase 3)."""
    logger = get_run_logger()
    logger.info(f"Carbon task for transition {transition} - not yet implemented")
    return {"transition": transition, "status": "placeholder"}


@flow(name="ingestion-flow", log_prints=True)
def ingestion_flow(
    service_account_email: str,
    key_file: str,
    project: str,
    epochs: list
):
    """Ingestion flow: GEE auth, Sentinel-2 composites, GEDI, MapBiomas (Phase 2)."""
    logger = get_run_logger()
    logger.info("Starting ingestion flow")

    initialise_gee(service_account_email, key_file, project)

    results = []
    for epoch in epochs:
        result = placeholder_ingestion(epoch)
        results.append(result)

    logger.info(f"Ingestion flow complete for epochs: {epochs}")
    return results


@flow(name="carbon-flow", log_prints=True)
def carbon_flow(transitions: list):
    """Carbon flow: change detection, biomass extraction, CO2e calculation (Phase 3)."""
    logger = get_run_logger()
    logger.info("Starting carbon flow")

    results = []
    for transition in transitions:
        result = placeholder_carbon(transition)
        results.append(result)

    logger.info("Carbon flow complete")
    return results