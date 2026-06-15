# src/pipeline/utils/gcs_utils.py

import boto3
from google.cloud import storage
from google.oauth2 import service_account
from prefect import get_run_logger


def get_gcs_client(key_file: str):
    """Return an authenticated GCS client using service account credentials."""
    credentials = service_account.Credentials.from_service_account_file(key_file)
    return storage.Client(credentials=credentials)


def delete_gcs_file(client, bucket_name: str, blob_name: str):
    """Delete a file from GCS after successful transfer to S3."""
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.delete()


def copy_gcs_to_s3(
    key_file: str,
    gcs_bucket: str,
    gcs_prefix: str,
    s3_bucket: str,
    s3_prefix: str,
    delete_after: bool = True
):
    """
    Copy all files under a GCS prefix to an S3 prefix.
    Optionally deletes GCS files after successful copy.
    Returns list of S3 keys written.
    """
    logger = get_run_logger()
    gcs_client = get_gcs_client(key_file)
    s3_client = boto3.client("s3", region_name="eu-north-1")

    bucket = gcs_client.bucket(gcs_bucket)
    blobs = list(bucket.list_blobs(prefix=gcs_prefix))

    if not blobs:
        logger.warning(f"No files found in GCS under gs://{gcs_bucket}/{gcs_prefix}")
        return []

    s3_keys = []
    for blob in blobs:
        filename = blob.name.split("/")[-1]
        s3_key = f"{s3_prefix}/{filename}"

        logger.info(f"Copying gs://{gcs_bucket}/{blob.name} -> s3://{s3_bucket}/{s3_key}")

        # stream from GCS to S3 via memory
        data = blob.download_as_bytes()
        s3_client.put_object(Body=data, Bucket=s3_bucket, Key=s3_key)
        s3_keys.append(s3_key)

        if delete_after:
            blob.delete()
            logger.info(f"Deleted GCS file: {blob.name}")

    logger.info(f"Transferred {len(s3_keys)} files from GCS to S3")
    return s3_keys