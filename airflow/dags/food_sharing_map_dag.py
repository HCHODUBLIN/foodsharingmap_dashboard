"""
Food Sharing Map Data Pipeline DAG

Fetches food sharing initiative data from the ShareCity200 REST API
and loads it into Snowflake bronze layer via S3.

Schedule: Runs twice a year (January 1 and July 1) to match data update cadence.
Manual trigger is also supported via Airflow REST API.

Flow:
    extract_and_upload_to_s3
        └── load_raw_to_snowflake (reads from S3 key)
                └── run_dbt_transformations
                        └── stop_ec2_instance
"""

import json
import logging
import subprocess
from datetime import datetime, timedelta, timezone

import requests
import snowflake.connector
from airflow import DAG
from airflow.decorators import task
from airflow.hooks.base import BaseHook
from airflow.providers.amazon.aws.hooks.s3 import S3Hook

logger = logging.getLogger(__name__)

API_URL = "https://www.sharingsolutions.eu/wp-json/cultivate/v1/data"
S3_BUCKET = "food-sharing-map-data-lake-prod"
S3_KEY_PREFIX = "raw/food_sharing_map"

default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="food_sharing_map_pipeline",
    default_args=default_args,
    description="Ingest Food Sharing Map data from REST API into Snowflake",
    schedule="0 0 1 1,7 *",  # January 1 and July 1
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["food_sharing_map", "data_pipeline", "snowflake"],
) as dag:

    @task()
    def extract_and_upload_to_s3() -> str:
        """Fetch data from the REST API and upload raw JSON to S3.

        Returns the S3 key so downstream tasks can read from S3
        instead of passing large payloads through XCom.
        """
        logger.info("Fetching data from %s", API_URL)
        response = requests.get(API_URL, timeout=60)
        response.raise_for_status()
        payload = response.json()

        # API returns {"success": ..., "data": [...]}
        if isinstance(payload, dict) and "data" in payload:
            data = payload["data"]
        else:
            data = payload

        if not isinstance(data, list):
            raise ValueError(
                f"Expected list from API, got {type(data).__name__}"
            )

        logger.info("Fetched %d records from API", len(data))

        # Upload to S3
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        s3_key = f"{S3_KEY_PREFIX}/{timestamp}/data.json"
        s3_hook = S3Hook(aws_conn_id="aws_default")
        s3_hook.load_string(
            string_data=json.dumps(data),
            key=s3_key,
            bucket_name=S3_BUCKET,
            replace=True,
        )
        logger.info("Uploaded raw data to s3://%s/%s", S3_BUCKET, s3_key)

        # Return only the S3 key (small string) via XCom
        return s3_key

    @task()
    def load_raw_to_snowflake(s3_key: str) -> None:
        """Load raw JSON data from S3 into Snowflake bronze table (append)."""
        # Read data from S3
        s3_hook = S3Hook(aws_conn_id="aws_default")
        raw_json = s3_hook.read_key(key=s3_key, bucket_name=S3_BUCKET)
        data = json.loads(raw_json)

        if not isinstance(data, list):
            raise ValueError(
                f"Expected list from S3 payload, got {type(data).__name__}"
            )

        ingestion_ts = datetime.now(timezone.utc).isoformat()
        conn_params = BaseHook.get_connection("snowflake_default")
        extra = json.loads(conn_params.extra) if conn_params.extra else {}

        conn = snowflake.connector.connect(
            user=conn_params.login,
            password=conn_params.password,
            account=extra.get("account", ""),
            warehouse=extra.get("warehouse", "FOOD_SHARING_ETL_WH"),
            database=extra.get("database", "FOOD_SHARING_MAP"),
            schema="BRONZE",
            role=extra.get("role", "FOOD_SHARING_ETL_ROLE"),
        )
        try:
            with conn.cursor() as cursor:
                # Create bronze table if not exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS
                        FOOD_SHARING_MAP.BRONZE.RAW_INITIATIVES (
                        id VARCHAR,
                        raw_json VARIANT,
                        ingested_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                        source_api VARCHAR
                            DEFAULT 'sharingsolutions_cultivate_v1'
                    )
                """)

                # Append records (preserves history)
                for r in data:
                    cursor.execute(
                        """
                        INSERT INTO FOOD_SHARING_MAP.BRONZE.RAW_INITIATIVES
                            (id, raw_json, ingested_at)
                        SELECT %s, PARSE_JSON(%s), %s
                        """,
                        (r.get("id"), json.dumps(r), ingestion_ts),
                    )

            conn.commit()
            logger.info(
                "Loaded %d records into BRONZE.RAW_INITIATIVES", len(data)
            )
        finally:
            conn.close()

    @task()
    def run_dbt_transformations() -> None:
        """Run dbt transformations (bronze -> silver -> gold) and tests."""
        dbt_dir = "/opt/dbt/food_sharing_map"

        # dbt run
        result = subprocess.run(
            [
                "dbt", "run",
                "--project-dir", dbt_dir,
                "--profiles-dir", dbt_dir,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        logger.info("dbt run stdout:\n%s", result.stdout)
        logger.info("dbt run stderr:\n%s", result.stderr)
        if result.returncode != 0:
            raise RuntimeError(
                f"dbt run failed (exit {result.returncode}):\n"
                f"{result.stdout}\n{result.stderr}"
            )

        # dbt test
        result = subprocess.run(
            [
                "dbt", "test",
                "--project-dir", dbt_dir,
                "--profiles-dir", dbt_dir,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        logger.info("dbt test stdout:\n%s", result.stdout)
        logger.info("dbt test stderr:\n%s", result.stderr)
        if result.returncode != 0:
            raise RuntimeError(
                f"dbt test failed (exit {result.returncode}):\n"
                f"{result.stdout}\n{result.stderr}"
            )

    @task()
    def stop_ec2_instance() -> None:
        """Stop this EC2 instance after pipeline completes."""
        import urllib.request

        import boto3

        # Get instance ID from EC2 metadata (IMDSv2)
        token = urllib.request.urlopen(
            urllib.request.Request(
                "http://169.254.169.254/latest/api/token",
                headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
                method="PUT",
            )
        ).read().decode()

        instance_id = urllib.request.urlopen(
            urllib.request.Request(
                "http://169.254.169.254/latest/meta-data/instance-id",
                headers={"X-aws-ec2-metadata-token": token},
            )
        ).read().decode()

        ec2 = boto3.client("ec2", region_name="eu-central-1")
        ec2.stop_instances(InstanceIds=[instance_id])
        logger.info("Stopping EC2 instance %s", instance_id)

    # DAG task dependencies
    s3_key = extract_and_upload_to_s3()
    load = load_raw_to_snowflake(s3_key)
    dbt_run = run_dbt_transformations()
    stop = stop_ec2_instance()

    # Sequential: extract → load → dbt → stop
    s3_key >> load >> dbt_run >> stop
