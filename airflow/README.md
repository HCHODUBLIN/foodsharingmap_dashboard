# Airflow — Data Pipeline Orchestration

Manages the end-to-end data ingestion pipeline for the Food Sharing Map project.

## DAG: `food_sharing_map_pipeline`

```
extract_and_upload_to_s3
    └── load_raw_to_snowflake
            └── run_dbt_transformations
                    └── stop_ec2_instance
```

| Task | Description |
|---|---|
| `extract_and_upload_to_s3` | Fetch ~3,000+ records from CULTIVATE REST API, upload raw JSON to S3, return S3 key via XCom |
| `load_raw_to_snowflake` | Read from S3, append records to `BRONZE.RAW_INITIATIVES` (history preserved) |
| `run_dbt_transformations` | Run `dbt run` + `dbt test` (bronze → silver → gold) |
| `stop_ec2_instance` | Self-stop EC2 to save costs |

### Design Decisions

- **S3-key handoff**: Only the S3 key is passed via XCom, not the full JSON payload
- **Append mode**: No truncate — each ingestion adds rows with a unique `ingested_at` timestamp, preserving history
- **API validation**: Checks that API response is a list before processing
- **Snowflake connection**: Uses context manager for cursor, explicit `commit()`, and `finally: conn.close()`

## Schedule

Semi-annual: `0 0 1 1,7 *` (January 1 and July 1)

Automated via **EventBridge → Lambda → EC2 start → Airflow DAG → EC2 stop**.

## Local Setup

```bash
# Build and start
docker compose up --build airflow-init
docker compose up -d

# Access Airflow UI
open http://localhost:8080
# Login: airflow / airflow
```

## Snowflake Connection

In the Airflow UI, set up the connection:

**Admin → Connections → Add**

| Field | Value |
|---|---|
| Conn ID | `snowflake_default` |
| Conn Type | Snowflake |
| Login | your Snowflake username |
| Password | your Snowflake password |
| Extra | `{"account": "HZWBPLU-HV69859", "warehouse": "FOOD_SHARING_ETL_WH", "database": "FOOD_SHARING_MAP", "role": "FOOD_SHARING_ETL_ROLE"}` |

## File Structure

```
airflow/
├── dags/
│   └── food_sharing_map_dag.py   # Pipeline DAG
├── plugins/                       # Custom Airflow plugins (empty)
├── Dockerfile                     # Airflow 2.8.1 + Python 3.11
├── docker-compose.yaml            # Local Airflow setup
└── requirements.txt               # Python dependencies
```
