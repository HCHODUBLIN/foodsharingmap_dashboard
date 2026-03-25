# =============================================================================
# Snowflake Resources
# =============================================================================

resource "snowflake_database" "food_sharing" {
  name    = "FOOD_SHARING_MAP"
  comment = "Food Sharing Map data warehouse - ShareCity200 initiative data"
}

resource "snowflake_schema" "bronze" {
  database = snowflake_database.food_sharing.name
  name     = "BRONZE"
  comment  = "Raw data ingested from REST API"
}

resource "snowflake_schema" "silver" {
  database = snowflake_database.food_sharing.name
  name     = "SILVER"
  comment  = "Cleaned and flattened data"
}

resource "snowflake_schema" "gold" {
  database = snowflake_database.food_sharing.name
  name     = "GOLD"
  comment  = "Aggregated data for dashboard consumption"
}

resource "snowflake_warehouse" "etl_wh" {
  name           = "FOOD_SHARING_ETL_WH"
  warehouse_size = "X-SMALL"
  auto_suspend   = 60
  auto_resume    = true
  comment        = "Warehouse for ETL operations"
}

resource "snowflake_warehouse" "dashboard_wh" {
  name           = "FOOD_SHARING_DASHBOARD_WH"
  warehouse_size = "X-SMALL"
  auto_suspend   = 60
  auto_resume    = true
  comment        = "Warehouse for dashboard queries"
}

# Storage integration for S3
resource "snowflake_storage_integration" "s3_integration" {
  name    = "FOOD_SHARING_S3_INT"
  type    = "EXTERNAL_STAGE"
  enabled = true

  storage_allowed_locations = ["s3://${aws_s3_bucket.data_lake.bucket}/"]
  storage_provider          = "S3"

  storage_aws_role_arn = aws_iam_role.airflow_role.arn
}

# =============================================================================
# Snowflake Roles & Grants
# =============================================================================

resource "snowflake_account_role" "sysadmin" {
  name    = "FOOD_SHARING_SYSADMIN"
  comment = "Sysadmin role for Food Sharing Map project"
}

resource "snowflake_account_role" "etl_role" {
  name    = "FOOD_SHARING_ETL_ROLE"
  comment = "ETL pipeline role - Airflow DAG"
}

resource "snowflake_account_role" "analyst_role" {
  name    = "FOOD_SHARING_ANALYST_ROLE"
  comment = "Read-only analyst role for team members"
}

# Role hierarchy: ETL_ROLE & ANALYST_ROLE -> SYSADMIN -> ACCOUNTADMIN
resource "snowflake_grant_account_role" "etl_to_sysadmin" {
  role_name        = snowflake_account_role.etl_role.name
  parent_role_name = snowflake_account_role.sysadmin.name
}

resource "snowflake_grant_account_role" "analyst_to_sysadmin" {
  role_name        = snowflake_account_role.analyst_role.name
  parent_role_name = snowflake_account_role.sysadmin.name
}

resource "snowflake_grant_account_role" "sysadmin_to_accountadmin" {
  role_name        = snowflake_account_role.sysadmin.name
  parent_role_name = "ACCOUNTADMIN"
}

# =============================================================================
# ETL Role grants — BRONZE/SILVER/GOLD access, ETL warehouse
# =============================================================================

resource "snowflake_grant_privileges_to_account_role" "etl_bronze_usage" {
  account_role_name = snowflake_account_role.etl_role.name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.bronze.name}\""
  }
}

resource "snowflake_grant_privileges_to_account_role" "etl_bronze_tables" {
  account_role_name = snowflake_account_role.etl_role.name
  privileges        = ["SELECT", "INSERT", "UPDATE", "DELETE"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.bronze.name}\""
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "etl_bronze_all_tables" {
  account_role_name = snowflake_account_role.etl_role.name
  privileges        = ["SELECT", "INSERT", "UPDATE", "DELETE"]
  on_schema_object {
    all {
      object_type_plural = "TABLES"
      in_schema          = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.bronze.name}\""
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "etl_bronze_create_table" {
  account_role_name = snowflake_account_role.etl_role.name
  privileges        = ["CREATE TABLE"]
  on_schema {
    schema_name = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.bronze.name}\""
  }
}

# ETL Role — BRONZE create view (dbt staging views)
resource "snowflake_grant_privileges_to_account_role" "etl_bronze_create_view" {
  account_role_name = snowflake_account_role.etl_role.name
  privileges        = ["CREATE VIEW"]
  on_schema {
    schema_name = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.bronze.name}\""
  }
}

# ETL Role — SILVER usage + create table (dbt intermediate)
resource "snowflake_grant_privileges_to_account_role" "etl_silver_usage" {
  account_role_name = snowflake_account_role.etl_role.name
  privileges        = ["USAGE", "CREATE TABLE"]
  on_schema {
    schema_name = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.silver.name}\""
  }
}

resource "snowflake_grant_privileges_to_account_role" "etl_silver_all_tables" {
  account_role_name = snowflake_account_role.etl_role.name
  privileges        = ["SELECT", "INSERT", "UPDATE", "DELETE"]
  on_schema_object {
    all {
      object_type_plural = "TABLES"
      in_schema          = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.silver.name}\""
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "etl_silver_future_tables" {
  account_role_name = snowflake_account_role.etl_role.name
  privileges        = ["SELECT", "INSERT", "UPDATE", "DELETE"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.silver.name}\""
    }
  }
}

# ETL Role — GOLD usage + create table (dbt marts)
resource "snowflake_grant_privileges_to_account_role" "etl_gold_usage" {
  account_role_name = snowflake_account_role.etl_role.name
  privileges        = ["USAGE", "CREATE TABLE"]
  on_schema {
    schema_name = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.gold.name}\""
  }
}

resource "snowflake_grant_privileges_to_account_role" "etl_gold_all_tables" {
  account_role_name = snowflake_account_role.etl_role.name
  privileges        = ["SELECT", "INSERT", "UPDATE", "DELETE"]
  on_schema_object {
    all {
      object_type_plural = "TABLES"
      in_schema          = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.gold.name}\""
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "etl_gold_future_tables" {
  account_role_name = snowflake_account_role.etl_role.name
  privileges        = ["SELECT", "INSERT", "UPDATE", "DELETE"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.gold.name}\""
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "etl_wh_usage" {
  account_role_name = snowflake_account_role.etl_role.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.etl_wh.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "etl_db_usage" {
  account_role_name = snowflake_account_role.etl_role.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.food_sharing.name
  }
}

# =============================================================================
# Analyst Role grants — SILVER & GOLD read-only, dashboard warehouse
# =============================================================================

resource "snowflake_grant_privileges_to_account_role" "analyst_silver_usage" {
  account_role_name = snowflake_account_role.analyst_role.name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.silver.name}\""
  }
}

resource "snowflake_grant_privileges_to_account_role" "analyst_silver_select" {
  account_role_name = snowflake_account_role.analyst_role.name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.silver.name}\""
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "analyst_gold_usage" {
  account_role_name = snowflake_account_role.analyst_role.name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.gold.name}\""
  }
}

resource "snowflake_grant_privileges_to_account_role" "analyst_gold_select" {
  account_role_name = snowflake_account_role.analyst_role.name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = "\"${snowflake_database.food_sharing.name}\".\"${snowflake_schema.gold.name}\""
    }
  }
}

resource "snowflake_grant_privileges_to_account_role" "analyst_wh_usage" {
  account_role_name = snowflake_account_role.analyst_role.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.dashboard_wh.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "analyst_db_usage" {
  account_role_name = snowflake_account_role.analyst_role.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.food_sharing.name
  }
}
