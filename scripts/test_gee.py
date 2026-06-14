# scripts/test_gee.py

import ee

# authenticate using service account JSON key
credentials = ee.ServiceAccountCredentials(
    email="carbon-pipeline-sa@mato-grosso-carbon.iam.gserviceaccount.com",
    key_file="config/gee-service-account.json"
)

ee.Initialize(credentials, project="mato-grosso-carbon")

# simple test: get a Sentinel-2 image count over Mato Grosso
aoi = ee.Geometry.Rectangle([-56.0, -13.0, -54.0, -11.0])
collection = (
    ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(aoi)
    .filterDate("2023-06-01", "2023-08-31")
)

count = collection.size().getInfo()
print(f"Sentinel-2 scenes found over test AOI: {count}")
print("GEE authentication successful.")