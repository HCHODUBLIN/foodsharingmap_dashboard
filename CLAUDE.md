# CLAUDE.md

## Project Overview

Food Sharing Map — an end-to-end data pipeline and dashboard for food sharing initiative data from the CULTIVATE REST API.

**Architecture**: CULTIVATE REST API → Airflow → Snowflake (medallion: bronze/silver/gold) → Streamlit dashboard
**Infrastructure**: Terraform (AWS S3 + Snowflake)

## Project Structure

- `airflow/dags/` — Airflow DAG for API ingestion → S3 backup → Snowflake load → dbt run
- `dbt/` — dbt project with bronze (views), silver (tables), gold (tables) layers
- `dashboard/app.py` — Streamlit dashboard (supports Snowflake mode and API-only demo mode)
- `terraform/` — IaC for AWS S3 and Snowflake resources

## Tech Stack

- **Python 3.10+**, **Apache Airflow 2.8**, **Snowflake**, **dbt-snowflake 1.7**
- **Streamlit 1.31**, **Plotly**, **Pandas**
- **Terraform 1.5+**

## Key Commands

```bash
# Dashboard (local)
cd dashboard && pip install -r requirements.txt && streamlit run app.py

# dbt
cd dbt && dbt run && dbt test

# Terraform
cd terraform && terraform init && terraform plan && terraform apply

# Airflow (Docker)
cd airflow && docker compose up -d
```

## Data Source

- API: `https://www.sharingsolutions.eu/wp-json/cultivate/v1/data`
- No authentication required
- ~500+ food sharing initiative records (JSON)

## dbt Model Layers

- **Bronze**: `src_raw_initiatives` (view over raw VARIANT JSON)
- **Silver**: `stg_initiatives`, `stg_initiatives_activities`, `stg_initiatives_sharing_methods`
- **Gold**: `fct_activity_distribution`, `fct_geo_distribution`, `fct_country_summary`

## Conventions

- dbt profile: `food_sharing_map` (uses env vars: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`)
- Snowflake database: `FOOD_SHARING_MAP`, schemas: `BRONZE`, `SILVER`, `GOLD`
- Separate warehouses: `FOOD_SHARING_ETL_WH` (pipeline), `FOOD_SHARING_DASHBOARD_WH` (queries)
- Pipeline schedule: semi-annual (`0 0 1 1,7 *`)
- Dashboard secrets: `dashboard/.streamlit/secrets.toml` (not committed)

## Evaluation Criteria (DE Zoomcamp)

| Category | 4 points (target) | Status |
|---|---|---|
| **Problem description** | Well described, clear what problem the project solves | Done |
| **Cloud** | Developed in the cloud + IaC tools used | Terraform done, need Airflow on EC2 |
| **Data ingestion** | End-to-end pipeline: multiple DAG steps, upload to data lake | DAG written, not yet deployed |
| **Data warehouse** | Tables partitioned/clustered with explanation | Snowflake clustering keys defined |
| **Transformations** | dbt, Spark, or similar | dbt models ready, not yet run |
| **Dashboard** | 2+ tiles | Streamlit app with multiple tiles |
| **Reproducibility** | Clear instructions, easy to run, code works | README exists |

**Extra credit (optional)**: tests, Makefile, CI/CD pipeline (GitHub Actions done)

## Working Rules

- **Do NOT edit files without asking first.** Always show the code and ask for confirmation before making changes.
- **One file at a time.** Do not batch-edit multiple files in a single step.
- **Ask whether the user wants to do it themselves** or wants Claude to apply the change.
- **Do not import unused libraries.** Only import what is actually used in the code.
- **Follow Black code style** for all Python files (double quotes, 88-char line length, trailing commas on multiline).
