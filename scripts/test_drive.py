# scripts/test_drive.py

from src.pipeline.utils.drive_utils import get_drive_service

service = get_drive_service("config/gee-service-account.json")
print("Drive service authenticated:", service is not None)

# list up to 5 files to confirm read access
results = service.files().list(pageSize=5, fields="files(id, name)").execute()
files = results.get("files", [])
print(f"Drive access confirmed. Files visible: {len(files)}")
for f in files:
    print(f"  {f['name']} ({f['id']})")