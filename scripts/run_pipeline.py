# scripts/run_pipeline.py

import yaml
from dotenv import load_dotenv
from src.pipeline.flows import ingestion_flow, carbon_flow

load_dotenv("config/.env")


def main():
    with open("config/pipeline_config.yaml", "r") as f:
        config = yaml.safe_load(f)

    ingestion_flow(
        service_account_email=config["gee"]["service_account_email"],
        key_file=config["gee"]["key_file"],
        project=config["gee"]["project"],
        epochs=config["epochs"]
    )

    carbon_flow(transitions=config["transitions"])


if __name__ == "__main__":
    main()