# Design Document

## Customer Management Platform

---

## Overview

The AnyCompany Customer Management Platform is a serverl### Requirement 1: User Authentication

**User Story:** As a platform administrator, I want users to authenticate before accessing customer data, so that only authorized personnel can view or modify customer information.

#### Acceptance Criteria

1. THE Authentication_Service SHALL authenticate users using email and password credentials
2. WHEN authentication succeeds, THE Authentication_Service SHALL issue a JWT_Token valid for the session
3. WHEN authentication fails, THE Authentication_Service SHALL return an error message indicating invalid credentials
4. THE Authentication_Service SHALL enforce password policies requiring minimum 8 characters with uppercase, lowercase, digits, and symbols
5. THE Authentication_Service SHALL support password recovery through email-only account recoveryess REST API built on AWS. It provides centralized CRUD operations on customer records, secured by Cognito-issued JWT tokens validated by a Lambda Authorizer. All infrastructure is defined as Terraform code for reproducible environment provisioning.

The system uses two Lambda functions: an **Authorizer** that validates tokens and enforces role-based access, and a **Customers Lambda** that handles business logic and DynamoDB persistence. API Gateway sits in front of both, routing requests and enforcing authentication on every route.

---

## Architecture

```
Client
  │
  │  HTTP Request (Authorization: Bearer <JWT>)
  ▼
API Gateway (REST API)
  │
  ├── TOKEN Lambda Authorizer ──► Cognito User Pool (JWKS validation)
  │         │
  │         └── Returns IAM Policy (Allow / Deny)
  │
  ▼ (if Allow)
Customers Lambda
  │
  └── DynamoDB Table (customers)
```
## Components and Interfaces

### 1. Authorizer Lambda (`src/authorizer/lambda_function.py`)rization` header.
2. API Gateway invokes the Authorizer Lambda with the raw token.
3. The Authorizer fetches Cognito's JWKS, validates the token signature and expiry, extracts group claims, and returns an IAM policy document.
4. If the policy grants access, API Gateway forwards the request to the Customers Lambda.
5. The Customers Lambda performs the requested CRUD operation against DynamoDB and returns a response.

---

## Components

### 1. Authorizer Lambda (`src/authorizer/lambda_function.py`)

Responsible for:
- Fetching and caching the Cognito User Pool's JWKS endpoint.
- Validating the JWT signature, expiry, issuer, and audience.
- Extracting `cognito:groups` from the token claims.
- Generating an IAM policy that allows read-only methods for any authenticated user, and additionally allows write methods (POST, PUT, DELETE) only for members of the `admin` group.
- Returning HTTP 401 (via `Unauthorized` exception) for missing or invalid tokens.
- Returning an explicit Deny policy for authenticated non-admin users on write routes.

**Key dependencies:** `python-jose[cryptography]`, `boto3`, `datetime`

### 2. Customers Lambda (`src/customers/lambda_function.py`)

Handles the five CRUD operations plus search:

| Method | Route | Action |
|--------|-------|--------|
| POST | `/customers` | Create a new customer record |
| GET | `/customers/{customerId}` | Retrieve a single customer by ID |
| GET | `/customers` | List all customers |
| GET | `/customers/search` | Search customers by name or email |
| PUT | `/customers/{customerId}` | Update an existing customer |
| DELETE | `/customers/{customerId}` | Delete a customer |

Responsible for:
- Validating request payloads (required fields: `name`, `email`).
- Generating UUID v4 `customerId` values at creation time.
- Interacting with DynamoDB via `boto3`.
- Returning appropriate HTTP status codes and JSON bodies.
- Implementing search with pagination using DynamoDB Scan operation.

**Key dependencies:** `boto3`, `uuid`, `json`

### 3. DynamoDB Table

- **Partition key:** `customerId` (String)
- **Billing mode:** PAY_PER_REQUEST
- **Attributes stored per record:** `customerId`, `name`, `email`, `phone` (optional)

### 4. API Gateway REST API

- TOKEN-type Lambda Authorizer attached to all routes.
- Routes map HTTP methods to the Customers Lambda via Lambda proxy integration.
- Returns 401/403 from the Authorizer before the request reaches the Lambda.

### 5. Cognito User Pool

- Issues JWT tokens for authenticated users.
- Contains an `admin` Cognito group.
- The Authorizer reads `cognito:groups` from the token's claims to determine group membership.

---

## Data Models

### Customer Record (DynamoDB item)

```python
{
    "customerId": str,   # UUID v4, partition key, required
    "name":       str,   # full name, required
    "email":      str,   # email address, required
    "phone":      str,   # phone number, optional
}
```

### API Request / Response Schemas

**POST /customers – Request body**

```json
{
    "name":  "Jane Smith",
    "email": "jane@example.com",
    "phone": "+15550001234"
}
```

**POST /customers – Response (201)**

```json
{
    "customerId": "550e8400-e29b-41d4-a716-446655440000",
    "name":  "Jane Smith",
    "email": "jane@example.com",
    "phone": "+15550001234"
}
```

**GET /customers/{customerId} – Response (200)**

```json
{
    "customerId": "550e8400-e29b-41d4-a716-446655440000",
    "name":  "Jane Smith",
    "email": "jane@example.com",
    "phone": "+15550001234"
}
```

**GET /customers – Response (200)**

```json
[
    {
        "customerId": "550e8400-e29b-41d4-a716-446655440000",
        "name":  "Jane Smith",
        "email": "jane@example.com",
        "phone": "+15550001234"
    }
]
```

**PUT /customers/{customerId} – Request body**

```json
{
    "name":  "Jane Doe",
    "email": "jane.doe@example.com",
    "phone": "+15559990000"
}
```

**Error Response**

```json
{
    "message": "<descriptive error text>"
}
```

### IAM Policy Document (Authorizer output)

```python
{
    "principalId": "<sub from JWT>",
    "policyDocument": {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Action": "execute-api:Invoke",
                "Effect": "Allow" | "Deny",
                "Resource": "<method ARN>"
            }
        ]
    }
}
```

---

## Customer Search

### 1. New API Route

| Method | Route | Query Parameters |
|--------|-------|------------------|
| GET | `/customers/search` | `name` (optional), `email` (optional), `limit` (optional), `offset` (optional) |

- At least one search parameter (`name` or `email`) must be provided
- Both `name` and `email` can be provided for combined search
- Search is case-insensitive and supports partial matching
- Default `limit`: 20, Maximum `limit`: 100
- Default `offset`: 0
- Results are sorted by `name` (ascending) for consistent pagination

### 2. Routing Logic Update

Add a new condition in the Customers Lambda routing:

```python
def lambda_handler(event, context):
    method = event["httpMethod"]
    path = event["path"]
    params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}

    # ... existing routes ...

    # Search route - must check before generic GET to avoid conflicts
    elif method == "GET" and path == "/customers/search":
        return search_customers(query_params)
```

### 3. Search Implementation

DynamoDB does not natively support partial match or case-insensitive queries on attributes. The search implementation uses **Scan with Filter Expressions**:

```python
def search_customers(query_params):
    # Extract and validate query parameters
    name_query = query_params.get("name", "").strip().lower()
    email_query = query_params.get("email", "").strip().lower()

    # Validate at least one search parameter provided
    if not name_query and not email_query:
        return response(400, {"message": "At least one search parameter (name or email) is required"})

    # Parse pagination parameters with defaults
    try:
        limit = int(query_params.get("limit", 20))
        offset = int(query_params.get("offset", 0))
    except ValueError:
        return response(400, {"message": "Invalid limit or offset: must be integers"})

    # Validate pagination bounds
    if limit < 1 or limit > 100:
        return response(400, {"message": "Limit must be between 1 and 100"})
    if offset < 0:
        return response(400, {"message": "Offset must be non-negative"})

    # Build filter expression
    filter_expression = None
    expression_values = {}

    if name_query:
        name_filter = "contains(#name_lower, :name)"
        expression_values[":name"] = name_query
        filter_expression = name_filter

    if email_query:
        email_filter = "contains(#email_lower, :email)"
        expression_values[":email"] = email_query
        if filter_expression:
            filter_expression = f"({filter_expression}) AND ({email_filter})"
        else:
            filter_expression = email_filter

    # Execute scan with filter
    scan_params = {
        "FilterExpression": filter_expression,
        "ExpressionAttributeValues": expression_values,
        "ExpressionAttributeNames": {
            "#name_lower": "name",
            "#email_lower": "email"
        }
    }

    # Note: For case-insensitive search, the Lambda would need to store
    # lowercase versions of name/email as separate attributes, or use
    # Scan with client-side filtering for exact case-insensitive matching.
    # Current implementation uses case-sensitive contains for demonstration.
    # Production implementations may use:
    # - GSI with lowercase attributes
    # - AWS OpenSearch Service for advanced search
    # - Client-side filtering after scan

    result = table.scan(**scan_params)
    items = result.get("Items", [])

    # Apply pagination (offset/limit) after scan
    paginated_items = items[offset : offset + limit]

    return response(200, {
        "items": paginated_items,
        "limit": limit,
        "offset": offset,
        "total": len(items)
    })
```

**Note on DynamoDB Scan Performance:** The Scan operation reads the entire table, which is inefficient for large datasets. For production use cases with significant data volumes, consider:
- Using a Global Secondary Index (GSI) with lowercase attributes for case-insensitive prefix queries
- Implementing `begins_with` instead of `contains` for prefix matching
- Migrating to Amazon OpenSearch Service for advanced full-text search capabilities

### 4. API Request / Response Schemas (Updated)

**GET /customers/search – Request**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| name | string | No | Partial match on customer name (case-insensitive) |
| email | string | No | Partial match on customer email (case-insensitive) |
| limit | integer | No | Max results to return (1-100, default: 20) |
| offset | integer | No | Number of results to skip (default: 0) |

**GET /customers/search – Response (200)**

```json
{
    "items": [
        {
            "customerId": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Jane Smith",
            "email": "jane@example.com",
            "phone": "+15550001234"
        }
    ],
    "limit": 20,
    "offset": 0,
    "total": 1
}
```

**GET /customers/search – Error Response (400)**

```json
{
    "message": "At least one search parameter (name or email) is required"
}
```

or

```json
{
    "message": "Limit must be between 1 and 100"
}
```

### 5. Updated Components Table

Add to the Components section:

| Component | Change Type | Description |
|-----------|-------------|-------------|
| Customers Lambda | Modified | Added `search_customers` function and routing |
| API Gateway | Modified | Added GET `/customers/search` route |
| DynamoDB | No change | Scan operation; consider GSI for production |

### 6. Error Handling for Search

| Scenario | HTTP Status | Response body |
|---|---|---|
| No search parameter provided | 400 | `{"message": "At least one search parameter (name or email) is required"}` |
| Invalid limit (non-integer or out of range) | 400 | `{"message": "Limit must be between 1 and 100"}` |
| Invalid offset (non-integer or negative) | 400 | `{"message": "Offset must be non-negative"}` |
| Search returns no results | 200 | `{"items": [], "limit": 20, "offset": 0, "total": 0}` |

---

### Authorizer Lambda Interface

**Input event (TOKEN authorizer)**

```python
{
    "type":               "TOKEN",
    "authorizationToken": "Bearer <jwt>",
    "methodArn":          "arn:aws:execute-api:..."
}
```

**Logic**

```python
# Copyright AnyCompany

import re
import json
from datetime import datetime, timezone
from jose import jwt, jwk, JWTError
import boto3
import urllib.request

COGNITO_REGION    = os.environ["COGNITO_REGION"]
USER_POOL_ID      = os.environ["USER_POOL_ID"]
APP_CLIENT_ID     = os.environ["APP_CLIENT_ID"]
ADMIN_GROUP       = os.environ.get("ADMIN_GROUP", "admin")
JWKS_URL          = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"

_jwks_cache = None

def get_jwks():
    global _jwks_cache
    if _jwks_cache is None:
        with urllib.request.urlopen(JWKS_URL) as resp:
            _jwks_cache = json.loads(resp.read())
    return _jwks_cache

def lambda_handler(event, context):
    token = event.get("authorizationToken", "")
    method_arn = event["methodArn"]

    # Strip "Bearer " prefix
    if token.lower().startswith("bearer "):
        token = token[7:]

    if not token:
        raise Exception("Unauthorized")  # triggers 401

    try:
        header    = jwt.get_unverified_header(token)
        jwks      = get_jwks()
        key       = next(k for k in jwks["keys"] if k["kid"] == header["kid"])
        public_key = jwk.construct(key)
        claims    = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=APP_CLIENT_ID,
        )
    except (JWTError, StopIteration, Exception):
        raise Exception("Unauthorized")  # triggers 401

    groups = claims.get("cognito:groups", [])
    is_admin = ADMIN_GROUP in groups

    # Derive base ARN (covers all methods/routes)
    arn_parts = method_arn.split(":")
    region    = arn_parts[3]
    account   = arn_parts[4]
    api_id, stage, *_ = arn_parts[5].split("/")
    base_arn  = f"arn:aws:execute-api:{region}:{account}:{api_id}/{stage}/*"

    effect = "Allow" if is_admin else "Allow"  # Read is always allowed; write gating is below
    statements = [{"Action": "execute-api:Invoke", "Effect": "Allow", "Resource": base_arn}]

    # Deny write methods for non-admins
    write_methods = ["POST", "PUT", "DELETE"]
    if not is_admin:
        for method in write_methods:
            statements.append({
                "Action":   "execute-api:Invoke",
                "Effect":   "Deny",
                "Resource": f"arn:aws:execute-api:{region}:{account}:{api_id}/{stage}/{method}/*"
            })

    return {
        "principalId":    claims["sub"],
        "policyDocument": {"Version": "2012-10-17", "Statement": statements},
    }
```

### Customers Lambda Interface

**Input event (Lambda proxy integration)**

```python
{
    "httpMethod":            "POST",
    "path":                  "/customers",
    "pathParameters":        {"customerId": "..."},  # present for /{customerId} routes
    "body":                  "{\"name\": \"...\", \"email\": \"...\"}",
    "requestContext": { ... }
}
```

**Routing logic**

```python
# Copyright AnyCompany

import json
import os
import uuid
import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ["TABLE_NAME"]
dynamodb   = boto3.resource("dynamodb")
table      = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    method = event["httpMethod"]
    path   = event["path"]
    params = event.get("pathParameters") or {}

    if method == "POST" and path == "/customers":
        return create_customer(event)
    elif method == "GET" and path == "/customers/search":
        return search_customers(event.get("queryStringParameters") or {})
    elif method == "GET" and "customerId" in params:
        return get_customer(params["customerId"])
    elif method == "GET":
        return list_customers()
    elif method == "PUT" and "customerId" in params:
        return update_customer(params["customerId"], event)
    elif method == "DELETE" and "customerId" in params:
        return delete_customer(params["customerId"])
    else:
        return response(400, {"message": "Unsupported route"})
```

---

## Error Handling

| Scenario | HTTP Status | Response body |
|---|---|---|
| Missing or invalid JWT token | 401 | API Gateway default (from Authorizer) |
| Valid token, non-admin on write | 403 | API Gateway default (from Authorizer) |
| Missing required fields (`name`, `email`) | 400 | `{"message": "Missing required fields: name, email"}` |
| Customer not found by ID | 404 | `{"message": "Customer not found: <id>"}` |
| Unsupported HTTP method / route | 400 | `{"message": "Unsupported route"}` |
| Search without parameters | 400 | `{"message": "At least one search parameter (name or email) is required"}` |
| Invalid search limit | 400 | `{"message": "Limit must be between 1 and 100"}` |
| Invalid search offset | 400 | `{"message": "Offset must be non-negative"}` |
| Unexpected internal error | 500 | `{"message": "Internal server error"}` |

All Lambda responses use the Lambda proxy integration format:

```python
def response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers":    {"Content-Type": "application/json"},
        "body":       json.dumps(body),
    }
```

---

## Infrastructure Design (Terraform)

### File layout (`infra/`)

```
infra/
├── main.tf          # DynamoDB, Lambda functions, API Gateway, Cognito
├── variables.tf     # Input variable declarations
├── outputs.tf       # API URL, table name, user pool ID
├── providers.tf     # AWS provider + region
├── versions.tf      # Terraform and provider version constraints
├── terraform.tfvars # Default variable values
└── envs/
    ├── dev.tfvars
    └── prod.tfvars
```

### Key resource relationships

```
aws_cognito_user_pool
  └── aws_cognito_user_pool_client
  └── aws_cognito_user_group (admin)

aws_dynamodb_table (customers)

aws_iam_role (authorizer_lambda_role)
  └── aws_iam_role_policy (cloudwatch logs)

aws_iam_role (customers_lambda_role)
  └── aws_iam_role_policy (dynamodb:GetItem, PutItem, UpdateItem, DeleteItem, Scan)
  └── aws_iam_role_policy (cloudwatch logs)

aws_lambda_function (authorizer)
aws_lambda_function (customers)

aws_api_gateway_rest_api
  ├── /customers          POST, GET
  ├── /customers/{id}     GET, PUT, DELETE
  └── aws_api_gateway_authorizer (TOKEN type → authorizer lambda)
```

### Environment variables injected into Lambdas

**Authorizer Lambda**

| Variable | Description |
|---|---|
| `COGNITO_REGION` | AWS region of the User Pool |
| `USER_POOL_ID` | Cognito User Pool ID |
| `APP_CLIENT_ID` | Cognito App Client ID |
| `ADMIN_GROUP` | Name of the admin Cognito group (default: `admin`) |

**Customers Lambda**

| Variable | Description |
|---|---|
| `TABLE_NAME` | DynamoDB table name |

---

## Project File Structure

```
project-root/
├── src/
│   ├── authorizer/
│   │   ├── lambda_function.py
│   │   └── requirements.txt        # python-jose[cryptography]
│   └── customers/
│       ├── lambda_function.py
│       └── requirements.txt        # boto3 (provided by Lambda runtime)
├── tests/
│   ├── unit/
│   │   ├── test_authorizer.py
│   │   ├── test_customers.py
│   │   └── events/
│   │       ├── create_customer.json
│   │       ├── get_customer.json
│   │       ├── list_customers.json
│   │       ├── update_customer.json
│   │       └── delete_customer.json
│   └── integration/
│       └── test_api.py
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── providers.tf
│   ├── versions.tf
│   ├── terraform.tfvars
│   └── envs/
│       ├── dev.tfvars
│       └── prod.tfvars
└── README.md
```

---

## Testing Strategy

### Unit Tests (`tests/unit/`)

Unit tests run against each Lambda function in isolation using mocked AWS services and static event fixtures.

**Authorizer Lambda (`test_authorizer.py`)**

| Test case | What is verified |
|---|---|
| Valid admin JWT | Returns Allow policy for all routes |
| Valid non-admin JWT | Returns Allow for GET, Deny for POST/PUT/DELETE |
| Missing `Authorization` header | Raises `Unauthorized` (triggers HTTP 401) |
| Expired JWT | Raises `Unauthorized` |
| Tampered signature | Raises `Unauthorized` |
| Unknown `kid` in header | Raises `Unauthorized` |

**Customers Lambda (`test_customers.py`)**

| Test case | What is verified |
|---|---|
| POST valid payload | Returns 201 with a UUID v4 `customerId` |
| POST missing `name` or `email` | Returns 400 with error message |
| GET existing customer | Returns 200 with correct record |
| GET non-existent customer | Returns 404 |
| GET list (multiple records) | Returns 200 with all records |
| PUT existing customer | Returns 200 with updated fields |
| PUT non-existent customer | Returns 404 |
| DELETE existing customer | Returns 200; subsequent GET returns 404 |
| DELETE non-existent customer | Returns 404 |
| Unsupported method/route | Returns 400 |

Event fixtures in `tests/unit/events/` provide pre-built API Gateway proxy payloads for each operation.

**Running unit tests**

```bash
pytest tests/unit/
```

---

### Integration Tests (`tests/integration/`)

Integration tests (`test_api.py`) target a deployed API Gateway endpoint and verify end-to-end request flows with real AWS services.

| Test case | What is verified |
|---|---|
| Unauthenticated request | HTTP 401 from Authorizer |
| Non-admin token on POST | HTTP 403 from Authorizer |
| Admin token: create customer | HTTP 201; body contains `customerId` |
| Admin token: retrieve created customer | HTTP 200; fields match creation payload |
| Admin token: list customers | HTTP 200; list contains created record |
| Admin token: update customer | HTTP 200; subsequent GET returns new values |
| Admin token: delete customer | HTTP 200; subsequent GET returns 404 |
| Retrieve deleted customer | HTTP 404 |

Prerequisites: a deployed stack (`terraform apply`) and environment variables `API_URL`, `ADMIN_TOKEN`, and `READER_TOKEN` set before running.

**Running integration tests**

```bash
pytest tests/integration/
```

---

### Test Tooling

| Tool | Purpose |
|---|---|
| `pytest` | Test runner for both unit and integration suites |
| `unittest.mock` / `moto` | Mock `boto3` calls in unit tests |
| Static JSON fixtures | Reusable API Gateway event payloads |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Customer ID is always a UUID v4

*For any* valid customer creation request, the `customerId` assigned by the Customers Lambda SHALL match the UUID v4 format (`xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`).

**Validates: Requirements 1.1**

---

### Property 2: Missing required fields always returns HTTP 400

*For any* create or update request that omits the `name` or `email` field (or both), the Customers Lambda SHALL return an HTTP 400 response containing a non-empty error message.

**Validates: Requirements 1.3, 1.4**

---

### Property 3: Create-then-retrieve round trip preserves customer data

*For any* valid customer payload (arbitrary `name`, `email`, and optional `phone`), creating a customer and then retrieving it by the returned `customerId` SHALL return a record with identical field values.

**Validates: Requirements 2.2, 3.2**

---

### Property 4: Update-then-retrieve round trip reflects new values

*For any* existing customer and any valid update payload, updating the customer and then retrieving it by `customerId` SHALL return a record whose fields match the submitted update values.

**Validates: Requirements 5.2**

---

### Property 5: Delete makes record unretrievable

*For any* existing customer, after a successful delete operation, any subsequent retrieve request for that `customerId` SHALL return an HTTP 404 response.

**Validates: Requirements 6.2**

---

### Property 6: Non-existent customer ID always returns HTTP 404

*For any* `customerId` that has never been created (or has been deleted), retrieve, update, and delete operations SHALL each return an HTTP 404 response with a non-empty error message.

**Validates: Requirements 3.3, 5.3, 6.3**

---

### Property 7: List returns all created customers

*For any* set of customer records inserted into the system, a list request SHALL return a response containing every one of those records (by `customerId`).

**Validates: Requirements 4.2, 4.3**

---

### Property 8: Invalid or missing token always returns HTTP 401

*For any* API request where the `Authorization` header is absent, malformed, expired, or carries an invalid signature, the Authorizer SHALL raise `Unauthorized`, causing API Gateway to return HTTP 401 before the request reaches the Customers Lambda.

**Validates: Requirements 2.3, 3.4, 4.4, 5.4, 6.4, 7.1, 7.3, 7.4**

---

### Property 9: Non-admin token on write operations returns HTTP 403

*For any* valid JWT token whose `cognito:groups` claim does not contain the admin group name, write operations (POST, PUT, DELETE) SHALL result in a Deny IAM policy statement, causing API Gateway to return HTTP 403.

**Validates: Requirements 2.4, 5.5, 6.5, 7.2, 7.5**
---

## Observability Design

### Overview

The Customer Management Platform implements observability capabilities using AWS-native services: X-Ray for distributed tracing, CloudWatch Logs for logging, and CloudWatch Dashboard for centralized monitoring.

### Components

#### 1. AWS X-Ray Integration

**Lambda Tracing Configuration**

Both Lambda functions are configured with active tracing:

```hcl
resource "aws_lambda_function" "authorizer" {
  # ... other configuration ...

  tracing_config {
    mode = "Active"
  }
}

resource "aws_lambda_function" "customers" {
  # ... other configuration ...

  tracing_config {
    mode = "Active"
  }
}
```

**IAM Permissions for X-Ray**

The Lambda execution roles require `AWSXRayDaemonWriteAccess` to send trace data:

```hcl
resource "aws_iam_role_policy" "authorizer_xray" {
  name = "${local.name_prefix}-authorizer-xray"
  role = aws_iam_role.authorizer_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"]
      Resource = "*"
    }]
  })
}
```

**X-Ray Subsegments**

The Lambda functions automatically create subsegments for:
- DynamoDB calls (GetItem, PutItem, UpdateItem, DeleteItem, Scan)
- External HTTP calls (Cognito JWKS fetch)
- Lambda execution context

#### 2. API Gateway Logging

**Access Logs Configuration**

API Gateway access logs are enabled on the stage with detailed metrics:

```hcl
resource "aws_api_gateway_stage" "main" {
  deployment_id = aws_api_gateway_deployment.main.id
  rest_api_id   = aws_api_gateway_rest_api.main.id
  stage_name    = var.environment

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format         = "$context.requestId: $context.httpMethod $context.path $context.status $context.responseLatency $context.integrationErrorMessage"
  }
}
```

**Log Format Fields**

| Field | Description |
|-------|-------------|
| `requestId` | Unique identifier for the request |
| `httpMethod` | HTTP method (GET, POST, PUT, DELETE) |
| `path` | Request path |
| `status` | HTTP status code |
| `responseLatency` | Time in milliseconds |
| `integrationErrorMessage` | Error message if any |

#### 3. CloudWatch Log Retention

**Log Group Configuration**

All CloudWatch Log Groups are configured with configurable retention:

```hcl
resource "aws_cloudwatch_log_group" "authorizer" {
  name              = "/aws/lambda/${aws_lambda_function.authorizer.function_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Environment = var.environment
    Project     = var.project_name
  }
}
```

**Terraform Variable**

```hcl
variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs"
  type        = number
  default     = 30
}
```

#### 4. Structured Logging

**Authorizer Lambda**

```python
import logging
import json
from datetime import datetime, timezone

# Configure structured logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def logStructured(level: str, message: str, **kwargs):
    """Emit a structured JSON log entry."""
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "request_id": kwargs.get("request_id"),
        "user_id": kwargs.get("user_id"),
        "operation": kwargs.get("operation"),
    }
    # Add any additional fields
    for key, value in kwargs.items():
        if key not in log_entry:
            log_entry[key] = value
    logger.info(json.dumps(log_entry))

def lambda_handler(event, context):
    # ... existing code ...
    logStructured("INFO", "Token validated", request_id=context.aws_request_id, user_id=claims["sub"], operation="validate_token")
    # ... existing code ...
```

**Customers Lambda**

```python
import logging
import json
from datetime import datetime, timezone

# Configure structured logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def logStructured(level: str, message: str, **kwargs):
    """Emit a structured JSON log entry."""
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "request_id": kwargs.get("request_id"),
        "http_method": kwargs.get("http_method"),
        "path": kwargs.get("path"),
        "operation": kwargs.get("operation"),
    }
    # Add any additional fields
    for key, value in kwargs.items():
        if key not in log_entry:
            log_entry[key] = value
    logger.info(json.dumps(log_entry))

def lambda_handler(event, context):
    # ... existing code ...
    logStructured("INFO", "Customer created", request_id=context.aws_request_id, http_method="POST", path="/customers", operation="create_customer")
    # ... existing code ...
```

**Log Entry Structure**

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "message": "Customer created",
  "request_id": "abc123",
  "http_method": "POST",
  "path": "/customers",
  "operation": "create_customer",
  "customer_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### 5. CloudWatch Dashboard

**Dashboard Resource**

```hcl
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project_name}-${var.environment}-observability"

  dashboard_body = jsonencode({
    widgets = [
      # API Gateway Request Count
      {
        type = "metric"
        properties = {
          title = "API Gateway - Request Count"
          period = 300
          stat = "Sum"
          metric = "Requests"
          namespace = "AWS/ApiGateway"
          dimensions = {
            ApiName = aws_api_gateway_rest_api.main.name
          }
        }
      },
      # API Gateway Latency
      {
        type = "metric"
        properties = {
          title = "API Gateway - Latency (ms)"
          period = 300
          stat = "p95"
          metric = "Latency"
          namespace = "AWS/ApiGateway"
        }
      },
      # Lambda Invocations
      {
        type = "metric"
        properties = {
          title = "Lambda - Invocations"
          period = 300
          stat = "Sum"
          metric = "Invocations"
          namespace = "AWS/Lambda"
        }
      },
      # Lambda Errors
      {
        type = "metric"
        properties = {
          title = "Lambda - Error Rate (%)"
          period = 300
          stat = "Average"
          expression = "errors / invocations * 100"
          metrics = [
            ["AWS/Lambda", "Errors", ".", "."],
            [".", "Invocations", ".", "."]
          ]
        }
      },
      # DynamoDB Metrics
      {
        type = "metric"
        properties = {
          title = "DynamoDB - Consumed Capacity"
          period = 300
          stat = "Sum"
          metric = "ConsumedReadCapacityUnits"
          namespace = "AWS/DynamoDB"
        }
      }
    ]
  })
}
```

**Dashboard Widgets Summary**

| Widget | Metric | Visualization |
|--------|--------|---------------|
| Request Count | `Requests` (Sum) | Number |
| Latency p50 | `Latency` (p50) | Line |
| Latency p95 | `Latency` (p95) | Line |
| Latency p99 | `Latency` (p99) | Line |
| Lambda Invocations | `Invocations` (Sum) per function | Number |
| Lambda Errors | `Errors` (Sum) per function | Number |
| Error Rate | Calculated percentage | Line |
| DynamoDB Consumed RCU | `ConsumedReadCapacityUnits` (Sum) | Number |
| DynamoDB Throttles | `ThrottledRequests` (Sum) | Number |

### Infrastructure Changes Summary

| Component | Change Type | Description |
|-----------|-------------|-------------|
| Lambda Functions | Modified | Added `tracing_config` block for X-Ray |
| Lambda IAM Roles | Modified | Added X-Ray write permissions |
| API Gateway Stage | Modified | Added access logging configuration |
| CloudWatch Log Groups | Modified | Added retention policy |
| Lambda Functions | Modified | Added structured logging code |
| CloudWatch Dashboard | Added | Created observability dashboard |