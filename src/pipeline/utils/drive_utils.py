# src/pipeline/utils/drive_utils.py

import time
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account


def get_drive_service(key_file: str):
    """Return an authenticated Google Drive API service client."""
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    credentials = service_account.Credentials.from_service_account_file(
        key_file, scopes=scopes
    )
    return build("drive", "v3", credentials=credentials)


def wait_for_drive_file(service, filename: str, folder_name: str, timeout_s: int = 1800) -> str:
    """
    Poll Google Drive until a file with the given name appears in the given folder.
    Returns the file ID when found. Raises TimeoutError if not found within timeout.
    """
    elapsed = 0
    poll_interval = 30

    while elapsed < timeout_s:
        results = service.files().list(
            q=f"name='{filename}.tif' and trashed=false",
            fields="files(id, name, parents)"
        ).execute()

        files = results.get("files", [])
        if files:
            return files[0]["id"]

        time.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(f"File {filename}.tif not found in Drive after {timeout_s}s")


def download_drive_file(service, file_id: str, local_path: str):
    """Download a file from Google Drive to a local path."""
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id)

    with open(local_path, "wb") as f:
        downloader = MediaIoBaseDownload(f, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
