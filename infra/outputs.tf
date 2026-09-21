# Copyright AnyCompany

output "api_url" {
  description = "Base URL of the deployed API Gateway stage"
  value       = aws_api_gateway_stage.main.invoke_url
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB customers table"
  value       = aws_dynamodb_table.customers.name
}

output "cognito_user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = aws_cognito_user_pool.main.id
}

output "cognito_app_client_id" {
  description = "ID of the Cognito App Client"
  value       = aws_cognito_user_pool_client.main.id
}
