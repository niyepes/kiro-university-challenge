# Project Structure

Based on AWS Prescriptive Guidance for the Terraform AWS provider.

```
project-root/
├── src/
│   ├── authorizer/
│   │   ├── lambda_function.py   # JWT validation, returns IAM policy
│   │   └── requirements.txt     # boto3, python-jose
│   └── users/
│       ├── lambda_function.py   # Customer CRUD handlers
│       └── requirements.txt     # boto3
├── tests/
│   ├── unit/
│   │   └── events/              # Sample API Gateway event payloads
│   └── integration/
├── infra/
│   ├── main.tf                  # Lambda, API Gateway, authorizer, IAM
│   ├── variables.tf             # Input variables
│   ├── outputs.tf               # API URL, function ARNs
│   ├── providers.tf             # AWS provider config
│   ├── versions.tf              # Terraform + provider version pins
│   ├── terraform.tfvars         # Default values
│   └── envs/
│       ├── dev.tfvars           # Dev environment overrides
│       └── prod.tfvars          # Prod environment overrides
└── README.md
```

## File responsibilities

| Path | Responsibility |
| --- | --- |
| `src/<fn>/lambda_function.py` | Lambda entry point with `lambda_handler(event, context)` |
| `src/<fn>/requirements.txt` | Python dependencies for that function |
| `infra/main.tf` | Core resources: Lambda functions, API Gateway, authorizer, IAM roles |
| `infra/variables.tf` | Declared input variables with types and defaults |
| `infra/outputs.tf` | Exported values such as the invoke URL |
| `infra/envs/*.tfvars` | Per-environment variable values |

## Conventions

- Lambda functions live under `src/`, each with `lambda_function.py` as the entry point.
- Terraform lives in `infra/` with standard file separation.
- Environment-specific variables live in `infra/envs/`.
- Every source file includes the standard copyright header.
