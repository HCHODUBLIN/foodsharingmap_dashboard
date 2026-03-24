# Terraform — Infrastructure as Code

Provisions all cloud resources for the Food Sharing Map pipeline.

## Resources

### AWS (`main.tf`)

| Resource | Purpose |
|---|---|
| S3 bucket | Raw API data backup (`food-sharing-map-data-lake-prod`) |
| IAM role + policy | Airflow EC2 access to S3 |
| EC2 (t2.medium) | Airflow host, started/stopped by Lambda |
| Security group | Ports 8080 (Airflow UI) and 22 (SSH) |
| Lambda function | Starts EC2 on schedule |
| EventBridge rule | Semi-annual cron (`0 0 1 1,7 ? *`) triggers Lambda |

### Snowflake (`snowflake.tf`)

| Resource | Purpose |
|---|---|
| Database | `FOOD_SHARING_MAP` |
| Schemas | `BRONZE`, `SILVER`, `GOLD` (medallion architecture) |
| Warehouses | `FOOD_SHARING_ETL_WH` (pipeline), `FOOD_SHARING_DASHBOARD_WH` (queries) |
| S3 integration | `FOOD_SHARING_S3_INT` for external stage access |
| Roles | `FOOD_SHARING_SYSADMIN`, `FOOD_SHARING_ETL_ROLE`, `FOOD_SHARING_ANALYST_ROLE` |

### Role Hierarchy

```
ACCOUNTADMIN (Terraform provider only)
└── FOOD_SHARING_SYSADMIN
    ├── FOOD_SHARING_ETL_ROLE      ← Airflow DAG (BRONZE read/write, ETL warehouse)
    └── FOOD_SHARING_ANALYST_ROLE  ← Team members (SILVER/GOLD read-only, dashboard warehouse)
```

## File Structure

```
terraform/
├── main.tf                  # AWS resources (S3, IAM, EC2, Lambda, EventBridge)
├── snowflake.tf             # Snowflake resources (DB, schemas, warehouses, roles, grants)
├── variables.tf             # Input variables
├── outputs.tf               # Resource outputs
├── providers.tf             # AWS + Snowflake provider config
├── terraform.tfvars.example # Example variable values (copy to terraform.tfvars)
└── lambda/
    ├── index.py             # Lambda function source
    └── start_airflow.zip    # Packaged Lambda deployment
```

## Usage

```bash
# 1. Configure credentials
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your Snowflake and AWS credentials

# 2. Initialize and apply
terraform init
terraform plan
terraform apply
```

## Authentication

- **AWS**: Uses default credentials (`~/.aws/credentials` or environment variables)
- **Snowflake**: RSA key-pair authentication (`~/.snowflake/rsa_key.p8`)
