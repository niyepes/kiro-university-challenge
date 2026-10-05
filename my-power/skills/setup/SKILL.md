---
name: setup
description: Scaffold and configure a serverless AWS customer API using Terraform, Lambda, and API Gateway. Use when setting up a new serverless project, wiring a Lambda authorizer, or standing up the infra/ Terraform stack.
---

# Serverless AWS Setup

This skill guides the setup of a serverless customer-management API on AWS. It
follows the project conventions used across AnyCompany: Terraform for IaC, Python
on AWS Lambda for compute, API Gateway for the REST surface, and a custom Lambda
authorizer for authentication.

## When to use this skill

Activate this skill when the user wants to:

- Bootstrap a new serverless project from scratch.
- Add or wire a Lambda authorizer to an API Gateway REST API.
- Create or extend the Terraform stack under `infra/`.
- Package Python Lambda functions for deployment.

## Project layout

Follow this structure (see `references/project-structure.md` for the full tree):

```
project-root/
├── src/
│   ├── authorizer/        # Lambda authorizer (JWT validation)
│   └── users/             # Customer CRUD handlers
├── tests/
│   ├── unit/
│   └── integration/
├── infra/                 # Terraform: main.tf, variables.tf, outputs.tf, ...
└── README.md
```

## Workflow: Bootstrap a serverless API

1. **Create the source tree.** Add `src/<function>/lambda_function.py` with a
   `lambda_handler(event, context)` entry point and a `requirements.txt`.
2. **Add copyright headers.** Every source file must start with the standard
   copyright header (project code standard).
3. **Write the Terraform stack.** Create the files in `infra/` with the standard
   separation: `main.tf`, `variables.tf`, `outputs.tf`, `providers.tf`,
   `versions.tf`, plus `envs/dev.tfvars` and `envs/prod.tfvars`.
4. **Package the Lambdas.** Zip each `src/<function>/` directory for deployment
   (Terraform `archive_file` data source or a build step).
5. **Wire the authorizer.** Attach the authorizer Lambda to API Gateway as a
   `REQUEST` or `TOKEN` authorizer. See `references/authorizer-pattern.md`.
6. **Deploy.** Run `terraform init`, `terraform plan`, then `terraform apply`
   with the appropriate `-var-file=envs/<env>.tfvars`.

## Workflow: Add a Lambda authorizer

1. Create `src/authorizer/lambda_function.py` that validates a JWT with
   `python-jose` and returns an IAM policy document.
2. Return `Allow`/`Deny` effect scoped to the invoked method ARN.
3. Register the authorizer in Terraform and reference it from each protected
   method. Full example in `references/authorizer-pattern.md`.

## Conventions

- Default AWS region: `us-east-1`.
- Primary language: Python on AWS Lambda.
- Environment-specific values live in `infra/envs/*.tfvars`.
- Tests: `pytest tests/unit/` and `pytest tests/integration/`.

## Validation

Before considering setup complete:

- `terraform validate` passes in `infra/`.
- `terraform plan` shows the expected resources.
- `pytest tests/` passes.

## Reference files

- `references/project-structure.md` — full directory tree and file responsibilities.
- `references/authorizer-pattern.md` — Lambda authorizer code and Terraform wiring.
- `references/terraform-commands.md` — common Terraform and testing commands.
