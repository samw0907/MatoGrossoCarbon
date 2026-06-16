# scripts/generate_figures.py

import os
import yaml
from dotenv import load_dotenv
from src.pipeline.utils.s3_utils import download_file
from src.visualisation.map_outputs import generate_all_figures

load_dotenv("config/.env")

RUN_ID = "2026-06-15_160919"


def main():
    with open("config/pipeline_config.yaml") as f:
        config = yaml.safe_load(f)

    bucket = config["s3"]["bucket"]
    vectors_local_dir = f"outputs/vectors/{RUN_ID}"
    os.makedirs(vectors_local_dir, exist_ok=True)

    # download patch GeoJSONs from S3
    for transition in config["transitions"]:
        s3_key = f"mato-grosso/runs/{RUN_ID}/vectors/deforestation_patches_{transition}.geojson"
        local_path = f"{vectors_local_dir}/deforestation_patches_{transition}.geojson"
        if not os.path.exists(local_path):
            download_file(bucket, s3_key, local_path)
        else:
            print(f"Using cached: {local_path}")

    figures = generate_all_figures(RUN_ID, vectors_local_dir)
    print("Figures generated:")
    for f in figures:
        print(f"  {f}")


if __name__ == "__main__":
    main()