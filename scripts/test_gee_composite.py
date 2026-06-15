# scripts/test_gee_composite.py

import ee
from src.pipeline.utils.gee_utils import initialise_gee, get_aoi_geometry, mask_s2_scl

initialise_gee(
    service_account_email="carbon-pipeline-sa@mato-grosso-carbon.iam.gserviceaccount.com",
    key_file="config/gee-service-account.json",
    project="mato-grosso-carbon"
)

aoi = get_aoi_geometry("config/study_area.geojson")

for epoch in ["2020", "2022", "2023"]:
    col = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(aoi)
        .filterDate(f"{epoch}-06-01", f"{epoch}-08-30")
        .map(mask_s2_scl)
    )
    count = col.size().getInfo()
    composite = col.median().select(["B2", "B4", "B5", "B8", "B11", "B12"])
    bands = composite.bandNames().getInfo()
    print(f"Epoch {epoch}: {count} scenes, bands: {bands}")

print("GEE composite test passed.")