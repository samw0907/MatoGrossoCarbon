# scripts/generate_charts.py

import os
import yaml
from dotenv import load_dotenv
from src.pipeline.utils.s3_utils import download_file
from src.visualisation.chart_outputs import generate_all_charts

load_dotenv("config/.env")

RUN_ID = "2026-06-15_160919"


def main():
    with open("config/pipeline_config.yaml") as f:
        config = yaml.safe_load(f)

    bucket = config["s3"]["bucket"]
    vectors_local_dir = f"outputs/vectors/{RUN_ID}"
    reports_local_dir = f"outputs/reports/{RUN_ID}"

    os.makedirs(vectors_local_dir, exist_ok=True)
    os.makedirs(reports_local_dir, exist_ok=True)

    # download vectors
    for transition in config["transitions"]:
        s3_key = f"mato-grosso/runs/{RUN_ID}/vectors/deforestation_patches_{transition}.geojson"
        local_path = f"{vectors_local_dir}/deforestation_patches_{transition}.geojson"
        if not os.path.exists(local_path):
            download_file(bucket, s3_key, local_path)
        else:
            print(f"Using cached: {local_path}")

    # download reports
    for transition in config["transitions"]:
        s3_key = f"mato-grosso/runs/{RUN_ID}/reports/carbon_summary_{transition}.json"
        local_path = f"{reports_local_dir}/carbon_summary_{transition}.json"
        if not os.path.exists(local_path):
            download_file(bucket, s3_key, local_path)
        else:
            print(f"Using cached: {local_path}")

    charts = generate_all_charts(RUN_ID, vectors_local_dir, reports_local_dir)
    print("Charts generated:")
    for c in charts:
        print(f"  {c}")


if __name__ == "__main__":
    main()