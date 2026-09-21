# Implementation Plan: Customer Management Platform

## Overview

Implement a serverless customer management API on AWS using Python Lambda functions, DynamoDB, API Gateway, a Cognito-backed Lambda Authorizer, and Terraform for all infrastructure. Tasks are sequenced so each step integrates cleanly into the previous one, ending with a fully wired and tested system.

## Tasks

- [x] 1. Project scaffolding and shared utilities
  - [x] 1.1 Create project directory structure and dependency files
    - Create `src/authorizer/` and `src/customers/` directories with placeholder `lambda_function.py` files containing the copyright header
    - Create `src/authorizer/requirements.txt` with `python-jose[cryptography]`
    - Create `src/customers/requirements.txt` (boto3 provided by Lambda runtime; list explicitly for local dev)
    - Create `tests/unit/`, `tests/unit/events/`, and `tests/integration/` directories with `__init__.py` files
    - _Requirements: 8.1, 8.3_

  - [x] 1.2 Create sample event fixtures for unit tests
    - Write `tests/unit/events/create_customer.json`, `get_customer.json`, `list_customers.json`, `update_customer.json`, `delete_customer.json` matching the API request schemas in the design
    - _Requirements: 1.1, 2.2, 3.2, 4.2, 5.2, 6.2_

- [x] 2. Customers Lambda — core CRUD implementation
  - [x] 2.1 Implement the `response` helper and routing skeleton in `src/customers/lambda_function.py`
    - Add copyright header
    - Import `json`, `os`, `uuid`, `boto3`
    - Implement `response(status_code, body)` helper returning the Lambda proxy integration dict
    - Implement `lambda_handler` with route dispatch (POST `/customers`, GET `/customers`, GET `/customers/{customerId}`, PUT `/customers/{customerId}`, DELETE `/customers/{customerId}`) returning 400 for unmatched routes
    - _Requirements: 2.1, 3.1, 4.1, 5.1, 6.1_

  - [x] 2.2 Implement `create_customer`
    - Parse JSON body; return 400 if `name` or `email` is missing
    - Generate UUID v4 `customerId`
    - Write item to DynamoDB; return 201 with the full customer record
    - _Requirements: 1.1, 1.3, 1.4, 2.2_

  - [ ]* 2.3 Write property test for `create_customer` — UUID format and missing-field validation
    - **Property 1: Customer ID is always a UUID v4** — for arbitrary valid payloads the returned `customerId` matches `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`
    - **Validates: Requirements 1.1**
    - **Property 2: Missing required fields always returns HTTP 400** — for any payload missing `name`, `email`, or both, assert status 400 and non-empty message
    - **Validates: Requirements 1.3, 1.4**

  - [x] 2.4 Implement `get_customer`
    - Fetch item from DynamoDB by `customerId`; return 200 with the record or 404 with a descriptive message
    - _Requirements: 3.2, 3.3_

  - [x] 2.5 Implement `list_customers`
    - Scan DynamoDB table; return 200 with array of all records (empty array when table is empty)
    - _Requirements: 4.2, 4.3_

  - [x] 2.6 Implement `update_customer`
    - Return 404 if item does not exist
    - Build a DynamoDB `UpdateExpression` from the request body fields (`name`, `email`, `phone`)
    - Return 200 with the updated record
    - _Requirements: 5.2, 5.3_

  - [x] 2.7 Implement `delete_customer`
    - Return 404 if item does not exist
    - Delete item from DynamoDB; return 200 confirming deletion
    - _Requirements: 6.2, 6.3_

  - [ ]* 2.8 Write property tests for round-trip and 404 behaviours
    - **Property 3: Create-then-retrieve round trip preserves customer data** — arbitrary name/email/phone; assert retrieved record equals created record
    - **Validates: Requirements 2.2, 3.2**
    - **Property 4: Update-then-retrieve round trip reflects new values** — arbitrary update payload; assert retrieved record matches update
    - **Validates: Requirements 5.2**
    - **Property 5: Delete makes record unretrievable** — after delete, GET returns 404
    - **Validates: Requirements 6.2**
    - **Property 6: Non-existent customer ID always returns HTTP 404** — random UUIDs never inserted; GET, PUT, DELETE each return 404
    - **Validates: Requirements 3.3, 5.3, 6.3**
    - **Property 7: List returns all created customers** — insert N records, assert all `customerId` values appear in list response
    - **Validates: Requirements 4.2, 4.3**

  - [ ]* 2.9 Write unit tests for `src/customers/lambda_function.py`
    - Cover each route handler with mocked DynamoDB using `unittest.mock`
    - Test happy paths, missing-field 400, not-found 404, and unsupported-route 400
    - Use event fixtures from `tests/unit/events/`
    - _Requirements: 1.4, 2.2, 3.2, 3.3, 4.2, 4.3, 5.2, 5.3, 6.2, 6.3_

- [x] 3. Checkpoint — Customers Lambda
  - Ensure all Customers Lambda tests pass, ask the user if questions arise.

- [x] 4. Authorizer Lambda — JWT validation and IAM policy generation
  - [x] 4.1 Implement `src/authorizer/lambda_function.py` — JWKS fetch and JWT decode
    - Add copyright header
    - Read env vars: `COGNITO_REGION`, `USER_POOL_ID`, `APP_CLIENT_ID`, `ADMIN_GROUP`
    - Implement `get_jwks()` with module-level cache using `urllib.request`
    - Implement JWT decode: strip `Bearer ` prefix, fetch matching key by `kid`, decode with `python-jose` validating `RS256` algorithm and `audience`; raise `Exception("Unauthorized")` on any failure
    - _Requirements: 7.1, 7.3, 7.4_

  - [x] 4.2 Implement IAM policy generation in `src/authorizer/lambda_function.py`
    - Extract `cognito:groups` from claims; derive `base_arn` from `methodArn`
    - Always emit an Allow statement for `base_arn`
    - For non-admin callers, append Deny statements for `POST/*`, `PUT/*`, `DELETE/*` ARNs
    - Return `{"principalId": claims["sub"], "policyDocument": {...}}`
    - _Requirements: 7.2, 7.5, 2.3, 2.4, 5.4, 5.5, 6.4, 6.5_

  - [ ]* 4.3 Write property tests for the Authorizer Lambda
    - **Property 8: Invalid or missing token always returns HTTP 401** — for absent, malformed, expired, and bad-signature tokens, assert `Exception("Unauthorized")` is raised
    - **Validates: Requirements 2.3, 3.4, 4.4, 5.4, 6.4, 7.1, 7.3, 7.4**
    - **Property 9: Non-admin token on write operations returns HTTP 403** — for valid tokens without admin group, assert Deny statements present for POST/PUT/DELETE ARNs
    - **Validates: Requirements 2.4, 5.5, 6.5, 7.2, 7.5**

  - [ ]* 4.4 Write unit tests for `src/authorizer/lambda_function.py`
    - Mock `get_jwks()` and `jwt.decode`; test valid admin token, valid non-admin token, missing token, expired token, invalid signature
    - Assert correct IAM policy structure in each case
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 5. Checkpoint — Authorizer Lambda
  - Ensure all Authorizer Lambda tests pass, ask the user if questions arise.

- [x] 6. Terraform infrastructure
  - [x] 6.1 Create `infra/versions.tf` and `infra/providers.tf`
    - Pin Terraform `>= 1.5` and `hashicorp/aws ~> 5.0`
    - Configure AWS provider with `region = var.aws_region`
    - Add copyright header to each file
    - _Requirements: 8.1, 8.5_

  - [x] 6.2 Create `infra/variables.tf` and variable value files
    - Declare variables: `aws_region`, `environment`, `project_name`, `cognito_admin_group_name`
    - Create `infra/terraform.tfvars` with safe defaults
    - Create `infra/envs/dev.tfvars` and `infra/envs/prod.tfvars` with environment-specific overrides
    - _Requirements: 8.5_

  - [x] 6.3 Create DynamoDB table and Cognito resources in `infra/main.tf`
    - `aws_dynamodb_table` with `customerId` hash key, `PAY_PER_REQUEST` billing, and `ACTIVE` status
    - `aws_cognito_user_pool`, `aws_cognito_user_pool_client`, and `aws_cognito_user_group` for the admin group
    - Add copyright header
    - _Requirements: 8.1, 8.2_

  - [x] 6.4 Create IAM roles, Lambda functions, and Lambda zip archives in `infra/main.tf`
    - IAM execution roles for authorizer and customers Lambdas with CloudWatch Logs policies
    - Customers Lambda role gets DynamoDB `GetItem`, `PutItem`, `UpdateItem`, `DeleteItem`, `Scan` permissions on the table
    - `aws_lambda_function` resources for both Lambdas; inject required env vars; use `archive_file` data source to zip `src/authorizer/` and `src/customers/`
    - _Requirements: 8.3_

  - [x] 6.5 Create API Gateway REST API with TOKEN Authorizer in `infra/main.tf`
    - `aws_api_gateway_rest_api`, `/customers` resource, `/{customerId}` child resource
    - Methods: `POST` and `GET` on `/customers`; `GET`, `PUT`, `DELETE` on `/{customerId}`
    - Attach `aws_api_gateway_authorizer` (TOKEN type) to all methods
    - Lambda proxy integrations for all methods pointing to the Customers Lambda
    - `aws_api_gateway_deployment` and `aws_api_gateway_stage`
    - _Requirements: 8.4_

  - [x] 6.6 Create `infra/outputs.tf`
    - Output `api_url`, `dynamodb_table_name`, `cognito_user_pool_id`, `cognito_app_client_id`
    - _Requirements: 8.1, 8.2, 8.4_

- [x] 7. Checkpoint — Terraform
  - Run `terraform init` and `terraform validate` inside `infra/`; ensure all unit tests still pass. Ask the user if questions arise.

- [x] 8. Integration wiring and integration tests
  - [x] 8.1 Write integration tests in `tests/integration/test_api.py`
    - Read API URL and Cognito outputs from environment variables or Terraform outputs
    - Test create, retrieve, list, update, delete using real HTTP calls against the deployed API
    - Test 401 (no token) and 403 (non-admin token on write) scenarios
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 9. Final checkpoint — full test suite
  - Ensure all unit and property-based tests pass (`pytest tests/unit/`). Ask the user if questions arise.

- [x] 10. Customer Search
  - [x] 10.1 Add search route in Customers Lambda routing logic
    - Add GET `/customers/search` route to `lambda_handler` in `src/customers/lambda_function.py`
    - Route should parse query string parameters for name, email, limit, and offset
    - _Requirements: 9.1, 9.4_

  - [x] 10.2 Implement `search_customers` function
    - Use DynamoDB Scan with FilterExpression for partial case-insensitive matching
    - Support filtering by name (contains), email (contains), or both
    - Implement pagination with limit and offset parameters (default limit: 20)
    - Return array of matching customer records with count metadata
    - _Requirements: 9.2, 9.3, 9.5, 9.6, 9.7, 9.8_

  - [x] 10.3 Validate search parameters
    - Return 400 if limit is provided but less than 1
    - Return 400 if offset is provided but less than 0
    - Return 400 if neither name nor email query parameters are provided
    - _Requirements: 9.9, 9.10, 9.11_

  - [ ]* 10.4 Write unit tests for `search_customers` function
    - Test name search with partial case-insensitive match
    - Test email search with partial case-insensitive match
    - Test combined name and email search
    - Test pagination with limit and offset
    - Test edge cases: empty results, limit=1, offset at end of results
    - Test validation errors: missing search params, invalid limit, negative offset
    - _Requirements: 9.2, 9.3, 9.5, 9.6, 9.7, 9.8, 9.9, 9.10, 9.11_

- [x] 11. Search Integration (Terraform API Gateway)
  - [x] 11.1 Add `/customers/search` route in Terraform API Gateway configuration
    - Add GET method on `/customers/search` resource in `infra/main.tf`
    - Attach Lambda authorizer to the new method
    - _Requirements: 9.1_

- [x] 12. Final checkpoint — Search implementation
  - Ensure all search-related tests pass. Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical boundaries
- Property tests validate universal correctness properties using Hypothesis or a comparable PBT library
- Unit tests use `pytest` with `unittest.mock` for DynamoDB and JWKS calls
- All source files must include the AnyCompany copyright header per code standards

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "6.1", "6.2"] },
    { "id": 2, "tasks": ["2.2", "2.5", "6.3"] },
    { "id": 3, "tasks": ["2.3", "2.4", "2.6", "2.7", "6.4"] },
    { "id": 4, "tasks": ["2.8", "2.9", "4.1", "6.5"] },
    { "id": 5, "tasks": ["4.2", "6.6"] },
    { "id": 6, "tasks": ["4.3", "4.4"] },
    { "id": 7, "tasks": ["8.1"] },
    { "id": 8, "tasks": ["10.2", "11.1"] },
    { "id": 9, "tasks": ["10.1", "10.3"] },
    { "id": 10, "tasks": ["10.4"] },
    { "id": 11, "tasks": ["12"] }
  ]
}
```
- [ ] 13. Observability Infrastructure
  - [ ] 13.1 Enable X-Ray tracing for Authorizer Lambda
    - Add `aws_xray_trace_sampling_rule` resource for sampling configuration
    - Update Authorizer Lambda IAM role with `AWSXRayDaemonWriteAccess` policy
    - Add `tracing_config` block to Authorizer Lambda in Terraform with mode `active`
    - _Requirements: 10.1, 10.2_

  - [ ] 13.2 Enable X-Ray tracing for Customers Lambda
    - Update Customers Lambda IAM role with `AWSXRayDaemonWriteAccess` policy
    - Add `tracing_config` block to Customers Lambda in Terraform with mode `active`
    - _Requirements: 10.1, 10.2, 10.3_

  - [ ] 13.3 Enable API Gateway execution logging
    - Add `access_logs_settings` block to API Gateway stage in Terraform
    - Configure log format to include request path, HTTP method, status code, and latency
    - Create CloudWatch Log Group for API Gateway access logs
    - _Requirements: 11.1, 11.2, 11.3_

  - [ ] 13.4 Configure CloudWatch Log retention policy
    - Add `retention_in_days` variable to Terraform for configurable log retention
    - Set default retention to 30 days in `terraform.tfvars`
    - Apply retention policy to Lambda function CloudWatch Log Groups
    - Apply retention policy to API Gateway CloudWatch Log Groups
    - _Requirements: 12.1, 12.2, 12.3, 12.4_

  - [ ] 13.5 Add structured logging to Authorizer Lambda
    - Import `logging` and `json` modules
    - Configure root logger with JSON formatter
    - Add logging statements for: token validation, policy generation, errors
    - Include request_id, user_id, and operation outcome in log output
    - _Requirements: 13.1, 13.3, 13.4, 13.5_

  - [ ] 13.6 Add structured logging to Customers Lambda
    - Configure root logger with JSON formatter
    - Add logging statements for: each CRUD operation, search operations, errors
    - Include request_id, http_method, path, and operation result in log output
    - _Requirements: 13.2, 13.3, 13.4, 13.5_

  - [ ] 13.7 Create CloudWatch Observability Dashboard
    - Create `aws_cloudwatch_dashboard` resource with name `${project_name}-${environment}-observability`
    - Add widget for API Gateway request count (Sumo metric)
    - Add widget for API Gateway latency (p50, p95, p99)
    - Add widget for Lambda invocation counts per function
    - Add widget for Lambda error rates (errors / invocations * 100)
    - Add widget for DynamoDB consumed capacity and throttles
    - Configure dashboard to auto-refresh every 5 minutes
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7_

  - [ ] 13.8 Verify observability stack
    - Run `terraform validate` to ensure all new resources are valid
    - Run unit tests to ensure Lambda code changes don't break functionality
    - Test that structured logs are emitted correctly using mock logger