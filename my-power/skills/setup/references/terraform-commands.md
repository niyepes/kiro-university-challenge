# Common Commands

## Terraform

Run from the `infra/` directory.

```bash
terraform init                              # Download providers, init backend
terraform validate                          # Validate configuration syntax
terraform plan  -var-file=envs/dev.tfvars   # Preview changes for dev
terraform apply -var-file=envs/dev.tfvars   # Apply changes to dev
terraform apply -var-file=envs/prod.tfvars  # Apply changes to prod
terraform destroy -var-file=envs/dev.tfvars # Tear down dev
```

## Testing

Run from the project root.

```bash
pytest tests/unit/          # Unit tests
pytest tests/integration/   # Integration tests
pytest tests/               # All tests
```

## Packaging Lambdas

Prefer the Terraform `archive_file` data source so packaging is reproducible:

```hcl
data "archive_file" "authorizer" {
  type        = "zip"
  source_dir  = "${path.module}/../src/authorizer"
  output_path = "${path.module}/../.terraform/authorizer.zip"
}
```
