# src/pipeline/utils/s3_utils.py

import boto3
import s3fs
from botocore.exceptions import ClientError


def get_s3_client():
    """Return a boto3 S3 client using environment credentials."""
    return boto3.client("s3", region_name="eu-north-1")


def get_s3_fs():
    """Return an s3fs filesystem instance for rasterio-compatible S3 access."""
    return s3fs.S3FileSystem(anon=False)


def upload_file(local_path: str, bucket: str, s3_key: str) -> bool:
    """Upload a local file to S3. Returns True on success."""
    client = get_s3_client()
    try:
        client.upload_file(local_path, bucket, s3_key)
        print(f"Uploaded {local_path} to s3://{bucket}/{s3_key}")
        return True
    except ClientError as e:
        print(f"Upload failed: {e}")
        return False


def download_file(bucket: str, s3_key: str, local_path: str) -> bool:
    """Download a file from S3 to a local path. Returns True on success."""
    client = get_s3_client()
    try:
        client.download_file(bucket, s3_key, local_path)
        print(f"Downloaded s3://{bucket}/{s3_key} to {local_path}")
        return True
    except ClientError as e:
        print(f"Download failed: {e}")
        return False


def list_prefix(bucket: str, prefix: str) -> list:
    """List all object keys under a given S3 prefix."""
    client = get_s3_client()
    response = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    if "Contents" not in response:
        return []
    return [obj["Key"] for obj in response["Contents"]]


def upload_bytes(data: bytes, bucket: str, s3_key: str) -> bool:
    """Upload raw bytes to S3 (used for JSON reports and manifests)."""
    client = get_s3_client()
    try:
        client.put_object(Body=data, Bucket=bucket, Key=s3_key)
        print(f"Uploaded bytes to s3://{bucket}/{s3_key}")
        return True
    except ClientError as e:
        print(f"Bytes upload failed: {e}")
        return False