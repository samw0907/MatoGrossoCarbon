# src/pipeline/utils/gee_utils.py

import ee
import json


def initialise_gee(service_account_email: str, key_file: str, project: str):
    """Authenticate and initialise GEE using a service account."""
    credentials = ee.ServiceAccountCredentials(
        email=service_account_email,
        key_file=key_file
    )
    ee.Initialize(credentials, project=project)


def get_aoi_geometry(geojson_path: str) -> ee.Geometry:
    """Load AOI from a GeoJSON file and return as GEE Geometry."""
    with open(geojson_path) as f:
        geojson = json.load(f)
    feature = geojson["features"][0]
    return ee.Geometry(feature["geometry"])


def mask_s2_scl(image: ee.Image) -> ee.Image:
    """
    Apply SCL cloud masking to a Sentinel-2 image.
    Masks classes: 3 (cloud shadow), 8 (cloud medium), 9 (cloud high),
    10 (thin cirrus), 11 (snow/ice).
    """
    scl = image.select("SCL")
    mask = (
        scl.neq(3)
        .And(scl.neq(8))
        .And(scl.neq(9))
        .And(scl.neq(10))
        .And(scl.neq(11))
    )
    return image.updateMask(mask)