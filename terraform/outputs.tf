output "s3_bucket_name" {
  description = "S3 bucket name for data lake"
  value       = aws_s3_bucket.data_lake.bucket
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.data_lake.arn
}

output "snowflake_database" {
  description = "Snowflake database name"
  value       = snowflake_database.food_sharing.name
}

output "snowflake_etl_warehouse" {
  description = "Snowflake ETL warehouse name"
  value       = snowflake_warehouse.etl_wh.name
}

output "snowflake_dashboard_warehouse" {
  description = "Snowflake dashboard warehouse name"
  value       = snowflake_warehouse.dashboard_wh.name
}

output "airflow_ec2_instance_id" {
  description = "Airflow EC2 instance ID"
  value       = aws_instance.airflow.id
}

output "airflow_ec2_public_ip" {
  description = "Airflow EC2 public IP (when running)"
  value       = aws_instance.airflow.public_ip
}

output "lambda_start_airflow_arn" {
  description = "Lambda function ARN for starting Airflow"
  value       = aws_lambda_function.start_airflow.arn
}
