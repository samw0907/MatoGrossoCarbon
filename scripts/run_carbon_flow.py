# scripts/run_carbon_flow.py

import yaml
from dotenv import load_dotenv
from src.pipeline.flows import carbon_flow

load_dotenv("config/.env")


def main():
    with open("config/pipeline_config.yaml", "r") as f:
        config = yaml.safe_load(f)

    config["aoi_path"] = "config/study_area.geojson"

    # use the existing run_id from the completed ingestion flow
    run_id = "2026-06-15_160919"

    carbon_flow(run_id=run_id, config=config)


if __name__ == "__main__":
    main()