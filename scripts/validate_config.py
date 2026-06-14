# scripts/validate_config.py

import yaml
import json
import sys
from pathlib import Path


REQUIRED_TOP_LEVEL_KEYS = [
    "gee", "s3", "epochs", "transitions", "sentinel2",
    "gedi", "mapbiomas", "prodes", "change_detection",
    "carbon", "aoi", "outputs"
]

REQUIRED_GEE_KEYS = ["service_account_email", "key_file", "project"]
REQUIRED_S3_KEYS = ["bucket", "region"]


def validate_config(config_path: str, aoi_path: str) -> bool:
    errors = []

    # check config file exists
    if not Path(config_path).exists():
        print(f"ERROR: config file not found: {config_path}")
        return False

    with open(config_path) as f:
        config = yaml.safe_load(f)

    # check top level keys
    for key in REQUIRED_TOP_LEVEL_KEYS:
        if key not in config:
            errors.append(f"Missing top-level key: {key}")

    # check GEE keys
    for key in REQUIRED_GEE_KEYS:
        if key not in config.get("gee", {}):
            errors.append(f"Missing gee key: {key}")

    # check S3 keys
    for key in REQUIRED_S3_KEYS:
        if key not in config.get("s3", {}):
            errors.append(f"Missing s3 key: {key}")

    # check GEE key file exists
    key_file = config.get("gee", {}).get("key_file")
    if key_file and not Path(key_file).exists():
        errors.append(f"GEE key file not found: {key_file}")

    # check epochs and transitions are lists with values
    if not isinstance(config.get("epochs"), list) or len(config["epochs"]) == 0:
        errors.append("epochs must be a non-empty list")

    if not isinstance(config.get("transitions"), list) or len(config["transitions"]) == 0:
        errors.append("transitions must be a non-empty list")

    # check AOI file exists and is valid GeoJSON
    if not Path(aoi_path).exists():
        errors.append(f"AOI file not found: {aoi_path}")
    else:
        with open(aoi_path) as f:
            try:
                geojson = json.load(f)
                if geojson.get("type") != "FeatureCollection":
                    errors.append("AOI GeoJSON must be a FeatureCollection")
            except json.JSONDecodeError as e:
                errors.append(f"AOI GeoJSON is invalid: {e}")

    if errors:
        print("Config validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return False

    print("Config validation passed.")
    return True


if __name__ == "__main__":
    valid = validate_config("config/pipeline_config.yaml", "config/study_area.geojson")
    sys.exit(0 if valid else 1)