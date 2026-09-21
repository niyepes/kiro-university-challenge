# Copyright AnyCompany

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# DynamoDB Table
resource "aws_dynamodb_table" "customers" {
  name         = "${local.name_prefix}-customers"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "customerId"

  attribute {
    name = "customerId"
    type = "S"
  }

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# Cognito User Pool
resource "aws_cognito_user_pool" "main" {
  name = "${local.name_prefix}-user-pool"

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# Cognito App Client
resource "aws_cognito_user_pool_client" "main" {
  name         = "${local.name_prefix}-app-client"
  user_pool_id = aws_cognito_user_pool.main.id

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]
}

# Admin Cognito Group
resource "aws_cognito_user_group" "admin" {
  name         = var.cognito_admin_group_name
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Admin group with write access to customer records"
}

# ─── IAM: Shared assume-role policy ───────────────────────────────────────────
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ─── IAM: Authorizer Lambda ───────────────────────────────────────────────────
resource "aws_iam_role" "authorizer_lambda" {
  name               = "${local.name_prefix}-authorizer-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "authorizer_logs" {
  name = "${local.name_prefix}-authorizer-logs"
  role = aws_iam_role.authorizer_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "arn:aws:logs:*:*:*"
    }]
  })
}

# ─── IAM: Customers Lambda ────────────────────────────────────────────────────
resource "aws_iam_role" "customers_lambda" {
  name               = "${local.name_prefix}-customers-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

resource "aws_iam_role_policy" "customers_logs" {
  name = "${local.name_prefix}-customers-logs"
  role = aws_iam_role.customers_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "arn:aws:logs:*:*:*"
    }]
  })
}

resource "aws_iam_role_policy" "customers_dynamodb" {
  name = "${local.name_prefix}-customers-dynamodb"
  role = aws_iam_role.customers_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Scan",
      ]
      Resource = aws_dynamodb_table.customers.arn
    }]
  })
}

# ─── Lambda zip archives ──────────────────────────────────────────────────────
data "archive_file" "authorizer" {
  type        = "zip"
  source_dir  = "${path.module}/../src/authorizer"
  output_path = "${path.module}/../.terraform/authorizer.zip"
}

data "archive_file" "customers" {
  type        = "zip"
  source_dir  = "${path.module}/../src/customers"
  output_path = "${path.module}/../.terraform/customers.zip"
}

# ─── Lambda functions ─────────────────────────────────────────────────────────
resource "aws_lambda_function" "authorizer" {
  function_name    = "${local.name_prefix}-authorizer"
  role             = aws_iam_role.authorizer_lambda.arn
  filename         = data.archive_file.authorizer.output_path
  source_code_hash = data.archive_file.authorizer.output_base64sha256
  runtime          = "python3.12"
  handler          = "lambda_function.lambda_handler"

  environment {
    variables = {
      COGNITO_REGION = var.aws_region
      USER_POOL_ID   = aws_cognito_user_pool.main.id
      APP_CLIENT_ID  = aws_cognito_user_pool_client.main.id
      ADMIN_GROUP    = var.cognito_admin_group_name
    }
  }
}

resource "aws_lambda_function" "customers" {
  function_name    = "${local.name_prefix}-customers"
  role             = aws_iam_role.customers_lambda.arn
  filename         = data.archive_file.customers.output_path
  source_code_hash = data.archive_file.customers.output_base64sha256
  runtime          = "python3.12"
  handler          = "lambda_function.lambda_handler"

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.customers.name
    }
  }
}

# ─── API Gateway ──────────────────────────────────────────────────────────────

resource "aws_api_gateway_rest_api" "main" {
  name = "${local.name_prefix}-api"

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}

# Lambda Authorizer
resource "aws_api_gateway_authorizer" "token_authorizer" {
  name                   = "${local.name_prefix}-authorizer"
  rest_api_id            = aws_api_gateway_rest_api.main.id
  authorizer_uri         = aws_lambda_function.authorizer.invoke_arn
  authorizer_credentials = aws_iam_role.api_gateway_authorizer_invocation.arn
  type                   = "TOKEN"
  identity_source        = "method.request.header.Authorization"
}

# IAM role allowing API Gateway to invoke the authorizer Lambda
resource "aws_iam_role" "api_gateway_authorizer_invocation" {
  name = "${local.name_prefix}-apigw-auth-invoke"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "apigateway.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "api_gateway_authorizer_invocation" {
  name = "${local.name_prefix}-apigw-auth-invoke"
  role = aws_iam_role.api_gateway_authorizer_invocation.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.authorizer.arn
    }]
  })
}

# /customers resource
resource "aws_api_gateway_resource" "customers" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_rest_api.main.root_resource_id
  path_part   = "customers"
}

# /customers/{customerId} resource
resource "aws_api_gateway_resource" "customer_id" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.customers.id
  path_part   = "{customerId}"
}

# /customers/search resource
resource "aws_api_gateway_resource" "customers_search" {
  rest_api_id = aws_api_gateway_rest_api.main.id
  parent_id   = aws_api_gateway_resource.customers.id
  path_part   = "search"
}

# Lambda permission for API Gateway to invoke customers Lambda
resource "aws_lambda_permission" "api_gateway_customers" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.customers.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.main.execution_arn}/*/*"
}

# ── POST /customers ──────────────────────────────────────────────────────────
resource "aws_api_gateway_method" "post_customers" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.customers.id
  http_method   = "POST"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.token_authorizer.id
}

resource "aws_api_gateway_integration" "post_customers" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.customers.id
  http_method             = aws_api_gateway_method.post_customers.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.customers.invoke_arn
}

# ── GET /customers ───────────────────────────────────────────────────────────
resource "aws_api_gateway_method" "get_customers" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.customers.id
  http_method   = "GET"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.token_authorizer.id
}

resource "aws_api_gateway_integration" "get_customers" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.customers.id
  http_method             = aws_api_gateway_method.get_customers.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.customers.invoke_arn
}

# ── GET /customers/{customerId} ──────────────────────────────────────────────
resource "aws_api_gateway_method" "get_customer" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.customer_id.id
  http_method   = "GET"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.token_authorizer.id
}

resource "aws_api_gateway_integration" "get_customer" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.customer_id.id
  http_method             = aws_api_gateway_method.get_customer.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.customers.invoke_arn
}

# ── PUT /customers/{customerId} ──────────────────────────────────────────────
resource "aws_api_gateway_method" "put_customer" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.customer_id.id
  http_method   = "PUT"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.token_authorizer.id
}

resource "aws_api_gateway_integration" "put_customer" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.customer_id.id
  http_method             = aws_api_gateway_method.put_customer.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.customers.invoke_arn
}

# ── DELETE /customers/{customerId} ───────────────────────────────────────────
resource "aws_api_gateway_method" "delete_customer" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.customer_id.id
  http_method   = "DELETE"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.token_authorizer.id
}

resource "aws_api_gateway_integration" "delete_customer" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.customer_id.id
  http_method             = aws_api_gateway_method.delete_customer.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.customers.invoke_arn
}

# ── GET /customers/search ────────────────────────────────────────────────────
resource "aws_api_gateway_method" "get_customers_search" {
  rest_api_id   = aws_api_gateway_rest_api.main.id
  resource_id   = aws_api_gateway_resource.customers_search.id
  http_method   = "GET"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.token_authorizer.id
}

resource "aws_api_gateway_integration" "get_customers_search" {
  rest_api_id             = aws_api_gateway_rest_api.main.id
  resource_id             = aws_api_gateway_resource.customers_search.id
  http_method             = aws_api_gateway_method.get_customers_search.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.customers.invoke_arn
}

# ── Deployment & Stage ───────────────────────────────────────────────────────
resource "aws_api_gateway_deployment" "main" {
  rest_api_id = aws_api_gateway_rest_api.main.id

  depends_on = [
    aws_api_gateway_integration.post_customers,
    aws_api_gateway_integration.get_customers,
    aws_api_gateway_integration.get_customer,
    aws_api_gateway_integration.put_customer,
    aws_api_gateway_integration.delete_customer,
    aws_api_gateway_integration.get_customers_search,
  ]

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = var.environment
}
