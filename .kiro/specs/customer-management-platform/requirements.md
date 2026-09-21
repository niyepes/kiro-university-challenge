# Requirements Document

## Introduction

This document defines the requirements for the AnyCompany Customer Management Platform MVP — a serverless REST API that provides centralized customer data storage and management. The platform exposes CRUD endpoints secured by AWS Cognito-based role authentication, backed by DynamoDB, and deployed as AWS Lambda functions behind API Gateway. Authenticated users may read customer records; only members of the admin Cognito group may create, update, or delete them.

## Glossary

- **API**: The REST API exposed via AWS API Gateway.
- **Authorizer**: The AWS Lambda Authorizer function that validates JWT tokens and enforces role-based access control.
- **AWS X-Ray**: A distributed tracing service that collects data about requests that travel through applications and AWS services.
- **CloudWatch Dashboard**: A customizable view of CloudWatch metrics and alarms for monitoring system health.
- **CloudWatch Logs**: A service for ingesting, storing, and querying log data from AWS resources.
- **Customer**: A record containing a unique customer ID, full name, email address, and phone number.
- **Customer ID**: A system-generated, globally unique identifier (UUID v4) assigned to each Customer at creation time.
- **Customers Lambda**: The AWS Lambda function that handles CRUD operations on Customer records.
- **DynamoDB Table**: The AWS DynamoDB table that stores all Customer records, with Customer ID as the partition key.
- **Cognito User Pool**: The AWS Cognito User Pool used to authenticate users and issue JWT tokens.
- **Admin Group**: The Cognito User Pool group whose members are authorized to create, update, and delete Customer records.
- **Authenticated User**: Any user who presents a valid JWT token issued by the Cognito User Pool.
- **JWT Token**: A JSON Web Token issued by the Cognito User Pool and included in the `Authorization` header of API requests.
- **IAM Policy**: The AWS Identity and Access Management policy document returned by the Authorizer to allow or deny API access.
- **Log Group**: A CloudWatch Logs container for log streams from a specific AWS resource.
- **Log Retention**: The period of time that CloudWatch Logs retains log events before deletion.
- **Structured Logging**: JSON-formatted log entries with consistent fields for efficient analysis.
- **Trace Context**: Metadata propagated between services to enable distributed tracing.

---

## Requirements

### Requirement 1: Customer Data Model

**User Story:** As a customer service representative, I want each customer record to contain a unique ID, full name, email address, and phone number, so that I have a consistent and complete set of contact information for every customer.

#### Acceptance Criteria

1. THE Customers Lambda SHALL assign a UUID v4 Customer ID to each Customer record at creation time.
2. THE DynamoDB Table SHALL store each Customer record with the attributes: `customerId` (partition key), `name`, `email`, and `phone`.
3. WHEN a Customer record is stored, THE DynamoDB Table SHALL enforce the presence of the `customerId`, `name`, and `email` attributes.
4. IF a create request omits the `name` or `email` field, THEN THE Customers Lambda SHALL return an HTTP 400 response with a descriptive error message.

---

### Requirement 2: Create Customer

**User Story:** As an admin user, I want to create a new customer record via a REST endpoint, so that I can add new customers to the centralized system.

#### Acceptance Criteria

1. WHEN a POST request is received at `/customers` with a valid JWT token belonging to the Admin Group, THE API SHALL route the request to the Customers Lambda.
2. WHEN the Customers Lambda receives a valid create request, THE Customers Lambda SHALL persist the new Customer record in the DynamoDB Table and return an HTTP 201 response containing the created Customer record including the generated `customerId`.
3. IF the JWT token is missing or invalid, THEN THE Authorizer SHALL return an HTTP 401 response and THE API SHALL not route the request to the Customers Lambda.
4. IF the authenticated user is not a member of the Admin Group, THEN THE Authorizer SHALL return an HTTP 403 response and THE API SHALL not route the request to the Customers Lambda.

---

### Requirement 3: Retrieve Customer

**User Story:** As an authenticated user, I want to retrieve a customer record by ID via a REST endpoint, so that I can quickly look up a customer's contact information.

#### Acceptance Criteria

1. WHEN a GET request is received at `/customers/{customerId}` with a valid JWT token, THE API SHALL route the request to the Customers Lambda.
2. WHEN the Customers Lambda receives a valid retrieve request, THE Customers Lambda SHALL return an HTTP 200 response containing the Customer record matching the provided `customerId`.
3. IF no Customer record exists for the provided `customerId`, THEN THE Customers Lambda SHALL return an HTTP 404 response with a descriptive error message.
4. IF the JWT token is missing or invalid, THEN THE Authorizer SHALL return an HTTP 401 response and THE API SHALL not route the request to the Customers Lambda.

---

### Requirement 4: List Customers

**User Story:** As an authenticated user, I want to retrieve a list of all customer records via a REST endpoint, so that I can view the full customer base.

#### Acceptance Criteria

1. WHEN a GET request is received at `/customers` with a valid JWT token, THE API SHALL route the request to the Customers Lambda.
2. WHEN the Customers Lambda receives a valid list request, THE Customers Lambda SHALL return an HTTP 200 response containing an array of all Customer records stored in the DynamoDB Table.
3. WHEN the DynamoDB Table contains no Customer records, THE Customers Lambda SHALL return an HTTP 200 response containing an empty array.
4. IF the JWT token is missing or invalid, THEN THE Authorizer SHALL return an HTTP 401 response and THE API SHALL not route the request to the Customers Lambda.

---

### Requirement 5: Update Customer

**User Story:** As an admin user, I want to update an existing customer record via a REST endpoint, so that I can correct or refresh a customer's contact information.

#### Acceptance Criteria

1. WHEN a PUT request is received at `/customers/{customerId}` with a valid JWT token belonging to the Admin Group, THE API SHALL route the request to the Customers Lambda.
2. WHEN the Customers Lambda receives a valid update request, THE Customers Lambda SHALL update the matching Customer record in the DynamoDB Table with the provided field values and return an HTTP 200 response containing the updated Customer record.
3. IF no Customer record exists for the provided `customerId`, THEN THE Customers Lambda SHALL return an HTTP 404 response with a descriptive error message.
4. IF the JWT token is missing or invalid, THEN THE Authorizer SHALL return an HTTP 401 response and THE API SHALL not route the request to the Customers Lambda.
5. IF the authenticated user is not a member of the Admin Group, THEN THE Authorizer SHALL return an HTTP 403 response and THE API SHALL not route the request to the Customers Lambda.

---

### Requirement 6: Delete Customer

**User Story:** As an admin user, I want to delete a customer record via a REST endpoint, so that I can remove outdated or erroneous records from the system.

#### Acceptance Criteria

1. WHEN a DELETE request is received at `/customers/{customerId}` with a valid JWT token belonging to the Admin Group, THE API SHALL route the request to the Customers Lambda.
2. WHEN the Customers Lambda receives a valid delete request, THE Customers Lambda SHALL remove the matching Customer record from the DynamoDB Table and return an HTTP 200 response confirming deletion.
3. IF no Customer record exists for the provided `customerId`, THEN THE Customers Lambda SHALL return an HTTP 404 response with a descriptive error message.
4. IF the JWT token is missing or invalid, THEN THE Authorizer SHALL return an HTTP 401 response and THE API SHALL not route the request to the Customers Lambda.
5. IF the authenticated user is not a member of the Admin Group, THEN THE Authorizer SHALL return an HTTP 403 response and THE API SHALL not route the request to the Customers Lambda.

---

### Requirement 7: JWT Authentication and Authorization

**User Story:** As a system operator, I want all API requests to be authenticated via Cognito-issued JWT tokens, so that only authorized users can access customer data.

#### Acceptance Criteria

1. THE Authorizer SHALL validate the JWT token signature against the Cognito User Pool's public keys on every API request.
2. WHEN the JWT token is valid, THE Authorizer SHALL extract the user's Cognito group memberships and return an IAM Policy granting access to the appropriate API methods.
3. IF the JWT token is expired, THEN THE Authorizer SHALL return an HTTP 401 response.
4. IF the JWT token signature is invalid, THEN THE Authorizer SHALL return an HTTP 401 response.
5. WHILE processing a write operation (POST, PUT, DELETE), THE Authorizer SHALL verify membership in the Admin Group before issuing an allow IAM Policy.

---

### Requirement 8: Infrastructure Provisioning

**User Story:** As a developer, I want all platform infrastructure defined as Terraform code, so that environments can be provisioned and torn down consistently and repeatably.

#### Acceptance Criteria

1. THE Terraform configuration SHALL provision a DynamoDB Table with `customerId` as the partition key and pay-per-request billing mode.
2. THE Terraform configuration SHALL provision a Cognito User Pool and an Admin Group within that User Pool.
3. THE Terraform configuration SHALL provision the Authorizer Lambda and the Customers Lambda with the necessary IAM roles and policies to read from and write to the DynamoDB Table.
4. THE Terraform configuration SHALL provision an API Gateway REST API with the Authorizer Lambda configured as a TOKEN-type Lambda Authorizer on all routes.
5. THE Terraform configuration SHALL accept environment-specific variable values via `infra/envs/dev.tfvars` and `infra/envs/prod.tfvars`.

---

### Requirement 9: Search Customers

**User Story:** As an authenticated user, I want to search for customers by name or email using partial text matching, so that I can quickly find customers without knowing their exact details.

#### Acceptance Criteria

1. WHEN a GET request is received at `/customers/search` with a valid JWT token and a `name` query parameter, THE Customers Lambda SHALL return an HTTP 200 response containing all Customer records where the `name` attribute contains the provided search term as a case-insensitive partial match.
2. WHEN a GET request is received at `/customers/search` with a valid JWT token and an `email` query parameter, THE Customers Lambda SHALL return an HTTP 200 response containing all Customer records where the `email` attribute contains the provided search term as a case-insensitive partial match.
3. WHEN a GET request is received at `/customers/search` with a valid JWT token and both `name` and `email` parameters, THE Customers Lambda SHALL apply both filters and return Customer records matching both criteria.
4. WHEN a GET request is received at `/customers/search` with a valid JWT token and a `limit` query parameter, THE Customers Lambda SHALL return at most the specified number of Customer records in the response.
5. WHEN a GET request is received at `/customers/search` with a valid JWT token and an `offset` query parameter, THE Customers Lambda SHALL skip the specified number of Customer records before returning results.
6. WHEN the `limit` parameter is omitted, THE Customers Lambda SHALL use a default limit of 20 records.
7. WHEN the `offset` parameter is omitted, THE Customers Lambda SHALL start from the first record (offset 0).
8. IF the `limit` parameter is less than 1, THEN THE Customers Lambda SHALL return an HTTP 400 response with a descriptive error message.
9. IF the `offset` parameter is less than 0, THEN THE Customers Lambda SHALL return an HTTP 400 response with a descriptive error message.
10. IF no Customer records match the search criteria, THE Customers Lambda SHALL return an HTTP 200 response containing an empty array.
11. IF the JWT token is missing or invalid, THEN THE Authorizer SHALL return an HTTP 401 response and THE API SHALL not route the request to the Customers Lambda.
---

### Requirement 10: X-Ray Distributed Tracing

**User Story:** As a platform operator, I want distributed tracing enabled for all Lambda functions, so that I can identify performance bottlenecks and trace requests across services.

#### Acceptance Criteria

1. WHEN a Lambda function is invoked, THE AWS X-Ray SDK SHALL record trace data for the request.
2. THE X-Ray tracing SHALL be configured with read and write access permissions in the Lambda IAM role.
3. THE X-Ray tracing SHALL include subsegments for DynamoDB operations and external calls.
4. THE System SHALL propagate the X-Ray trace context to downstream services when applicable.

---

### Requirement 11: API Gateway Execution Logging

**User Story:** As a platform operator, I want API Gateway execution logs enabled, so that I can debug API requests and monitor usage patterns.

#### Acceptance Criteria

1. WHEN an API request is received, THE API Gateway SHALL log the request to CloudWatch Logs.
2. THE API Gateway execution logs SHALL include request path, HTTP method, response status code, and latency.
3. THE API Gateway SHALL log errors at the ERROR level and informational requests at the INFO level.
4. IF log level is not specified, THE API Gateway SHALL default to ERROR level logging.

---

### Requirement 12: CloudWatch Log Retention Policy

**User Story:** As a platform operator, I want a configurable log retention policy, so that I can balance storage costs with compliance requirements.

#### Acceptance Criteria

1. THE CloudWatch Log Groups SHALL have a configurable retention period.
2. WHILE no retention period is explicitly set, THE CloudWatch Log Groups SHALL retain logs for 30 days by default.
3. THE retention period SHALL be configurable via Terraform variables.
4. THE retention policy SHALL apply to all log groups created by the platform (Lambda execution logs, API Gateway logs).

---

### Requirement 13: Structured Logging in Lambda Functions

**User Story:** As a developer, I want Lambda functions to emit structured JSON logs, so that I can efficiently search and analyze logs using CloudWatch Logs Insights.

#### Acceptance Criteria

1. WHEN the Authorizer Lambda processes a request, THE Lambda SHALL emit JSON-formatted log entries containing the request ID, user ID, and operation outcome.
2. WHEN the Customers Lambda processes a request, THE Lambda SHALL emit JSON-formatted log entries containing the request ID, HTTP method, path, and operation result.
3. THE structured logs SHALL include a timestamp, log level, and correlation ID for each entry.
4. THE Lambda SHALL log at INFO level for successful operations and ERROR level for failures.
5. THE structured logs SHALL be emitted to the standard CloudWatch Logs output.

---

### Requirement 14: CloudWatch Observability Dashboard

**User Story:** As a platform operator, I want a centralized dashboard displaying key metrics, so that I can monitor system health and quickly identify issues.

#### Acceptance Criteria

1. THE System SHALL create a CloudWatch Dashboard with the name `${project_name}-${environment}-observability`.
2. THE Dashboard SHALL display API Gateway request count widget showing total requests over time.
3. THE Dashboard SHALL display API Gateway latency metrics (p50, p95, p99) as a line graph.
4. THE Dashboard SHALL display Lambda invocation counts per function as a metric widget.
5. THE Dashboard SHALL display Lambda error rates as a percentage of total invocations.
6. THE Dashboard SHALL display DynamoDB throttle events and consumed capacity units.
7. THE Dashboard SHALL auto-refresh at a 5-minute interval.