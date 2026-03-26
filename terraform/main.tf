# =============================================================================
# AWS Resources — S3
# =============================================================================

# S3 bucket for raw API data staging
resource "aws_s3_bucket" "data_lake" {
  bucket = "${var.project_name}-data-lake-${var.environment}"

  tags = {
    Project     = var.project_name
    Environment = var.environment
  }
}

resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    id     = "expire-old-raw-data"
    status = "Enabled"

    filter {
      prefix = "raw/"
    }

    expiration {
      days = 365
    }
  }
}

# =============================================================================
# AWS Resources — IAM
# =============================================================================

# IAM role for Airflow to access S3
resource "aws_iam_role" "airflow_role" {
  name = "${var.project_name}-airflow-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "airflow_s3_policy" {
  name = "${var.project_name}-airflow-s3-policy"
  role = aws_iam_role.airflow_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ]
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      }
    ]
  })
}

# =============================================================================
# EC2 — Airflow host (started/stopped by Lambda)
# =============================================================================

resource "aws_security_group" "airflow_sg" {
  name        = "${var.project_name}-airflow-sg"
  description = "Security group for Airflow EC2"

  ingress {
    description = "Airflow Web UI"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Project = var.project_name
  }
}

resource "aws_instance" "airflow" {
  ami                    = "ami-0a628e1e89aaedf80" # Amazon Linux 2023, eu-central-1
  instance_type          = "t2.medium"
  iam_instance_profile   = aws_iam_instance_profile.airflow_profile.name
  vpc_security_group_ids = [aws_security_group.airflow_sg.id]

  user_data = <<-EOF
    #!/bin/bash
    yum update -y
    yum install -y docker git
    systemctl enable docker
    systemctl start docker
    usermod -aG docker ec2-user
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
  EOF

  tags = {
    Name    = "${var.project_name}-airflow"
    Project = var.project_name
  }
}

resource "aws_iam_instance_profile" "airflow_profile" {
  name = "${var.project_name}-airflow-profile"
  role = aws_iam_role.airflow_role.name
}

# =============================================================================
# Lambda + EventBridge — EC2 start/stop scheduler
# =============================================================================

data "aws_region" "current" {}

resource "aws_iam_role" "lambda_ec2_role" {
  name = "${var.project_name}-lambda-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_ec2_policy" {
  name = "${var.project_name}-lambda-ec2-policy"
  role = aws_iam_role.lambda_ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ec2:StartInstances",
          "ec2:StopInstances",
          "ec2:DescribeInstances"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_lambda_function" "start_airflow" {
  function_name = "${var.project_name}-start-airflow"
  role          = aws_iam_role.lambda_ec2_role.arn
  handler       = "index.handler"
  runtime       = "python3.11"
  timeout       = 10

  filename         = "${path.module}/lambda/start_airflow.zip"
  source_code_hash = filebase64sha256("${path.module}/lambda/start_airflow.zip")

  environment {
    variables = {
      INSTANCE_ID = aws_instance.airflow.id
      REGION      = data.aws_region.current.name
    }
  }
}

resource "aws_cloudwatch_event_rule" "semi_annual_trigger" {
  name                = "${var.project_name}-semi-annual"
  description         = "Trigger Airflow pipeline Jan 1 and Jul 1"
  schedule_expression = "cron(0 0 1 1,7 ? *)"
}

resource "aws_cloudwatch_event_target" "start_airflow" {
  rule = aws_cloudwatch_event_rule.semi_annual_trigger.name
  arn  = aws_lambda_function.start_airflow.arn
}

resource "aws_lambda_permission" "eventbridge_invoke" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.start_airflow.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.semi_annual_trigger.arn
}

# =============================================================================
# API Gateway — HTTP trigger for Lambda (dashboard manual trigger)
# =============================================================================

resource "aws_apigatewayv2_api" "trigger_api" {
  name          = "${var.project_name}-trigger-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["Content-Type"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.trigger_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.trigger_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.start_airflow.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "trigger" {
  api_id    = aws_apigatewayv2_api.trigger_api.id
  route_key = "POST /trigger"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_lambda_permission" "apigw_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.start_airflow.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.trigger_api.execution_arn}/*/*"
}
