# scripts/test_s3.py

import os
import tempfile
from src.pipeline.utils.s3_utils import upload_file, download_file, list_prefix

BUCKET = "sam-carbon-pipeline"

# write a temp file and upload it
with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
    f.write("s3 connection test")
    tmp_path = f.name

upload_file(tmp_path, BUCKET, "test/connection_test.txt")

# list the prefix to confirm it arrived
keys = list_prefix(BUCKET, "test/")
print("Keys found:", keys)

# download it back
download_file(BUCKET, "test/connection_test.txt", tmp_path + "_download.txt")

with open(tmp_path + "_download.txt") as f:
    print("Downloaded content:", f.read())

os.unlink(tmp_path)
os.unlink(tmp_path + "_download.txt")
print("S3 round-trip test passed.")