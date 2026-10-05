# Lambda Authorizer Pattern

A custom Lambda authorizer validates a JWT and returns an IAM policy that tells
API Gateway whether to allow or deny the request.

## Handler (src/authorizer/lambda_function.py)

```python
# Copyright (c) AnyCompany. All rights reserved.
import os
from jose import jwt, JWTError


def _policy(principal_id, effect, resource):
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource,
                }
            ],
        },
    }


def lambda_handler(event, context):
    token = (event.get("authorizationToken") or "").replace("Bearer ", "")
    method_arn = event["methodArn"]

    try:
        claims = jwt.decode(
            token,
            os.environ["JWT_SECRET"],
            algorithms=["HS256"],
        )
    except JWTError:
        return _policy("user", "Deny", method_arn)

    return _policy(claims.get("sub", "user"), "Allow", method_arn)
```

## requirements.txt

```
boto3
python-jose
```

## Terraform wiring (infra/main.tf)

```hcl
resource "aws_api_gateway_authorizer" "jwt" {
  name                   = "jwt-authorizer"
  rest_api_id            = aws_api_gateway_rest_api.customers.id
  authorizer_uri         = aws_lambda_function.authorizer.invoke_arn
  authorizer_credentials = aws_iam_role.authorizer_invoke.arn
  type                   = "TOKEN"
  identity_source        = "method.request.header.Authorization"
}

resource "aws_api_gateway_method" "get_customer" {
  rest_api_id   = aws_api_gateway_rest_api.customers.id
  resource_id   = aws_api_gateway_resource.customer.id
  http_method   = "GET"
  authorization = "CUSTOM"
  authorizer_id = aws_api_gateway_authorizer.jwt.id
}
```

## Notes

- Return `Deny` on any validation failure; never raise to the client.
- Scope the policy `Resource` to the invoked `methodArn` to avoid over-granting.
- Store secrets in SSM Parameter Store or Secrets Manager, not in plain env vars,
  for production.
