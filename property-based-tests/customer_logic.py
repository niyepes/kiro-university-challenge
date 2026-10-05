# Copyright AnyCompany
"""Self-contained reference implementation of the Customer Management domain
logic, used as the system-under-test for the property-based test suite.

This module intentionally has NO dependency on AWS, boto3, or the (not yet
implemented) ``src/`` Lambda packages. It encapsulates the pure business rules
described in ``.kiro/specs/customer-management-platform/design.md`` so the
"Correctness Properties" declared there can be verified in isolation with
Hypothesis.

The three building blocks mirror the real system:

* ``response`` / ``create_customer`` / ``get_customer`` / ... reproduce the
  Customers Lambda proxy-integration contract (status codes + JSON bodies).
* ``CustomerStore`` is an in-memory stand-in for the DynamoDB table.
* ``build_authorizer_policy`` reproduces the TOKEN Lambda Authorizer output
  (the IAM policy document with Allow/Deny statements).
"""

import json
import re
import uuid

WRITE_METHODS = ("POST", "PUT", "DELETE")

UUID_V4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# ─── Lambda proxy response helper ─────────────────────────────────────────────
def response(status_code, body):
    """Build an API Gateway Lambda proxy integration response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


# ─── In-memory customer store (stands in for DynamoDB) ────────────────────────
class CustomerStore:
    """Minimal in-memory key/value store keyed by ``customerId``."""

    def __init__(self):
        self._items = {}

    def put(self, item):
        self._items[item["customerId"]] = dict(item)

    def get(self, customer_id):
        item = self._items.get(customer_id)
        return dict(item) if item is not None else None

    def delete(self, customer_id):
        self._items.pop(customer_id, None)

    def all(self):
        return [dict(v) for v in self._items.values()]

    def exists(self, customer_id):
        return customer_id in self._items


# ─── Validation ───────────────────────────────────────────────────────────────
def validate_payload(payload):
    """Return a list of missing required fields (``name``, ``email``)."""
    if not isinstance(payload, dict):
        return ["name", "email"]
    missing = []
    for field in ("name", "email"):
        value = payload.get(field)
        if value is None or (isinstance(value, str) and value.strip() == ""):
            missing.append(field)
    return missing


# ─── CRUD operations (mirror the Customers Lambda handlers) ───────────────────
def create_customer(store, payload):
    missing = validate_payload(payload)
    if missing:
        return response(400, {"message": f"Missing required fields: {', '.join(missing)}"})

    item = {
        "customerId": str(uuid.uuid4()),
        "name": payload["name"],
        "email": payload["email"],
    }
    if payload.get("phone") is not None:
        item["phone"] = payload["phone"]

    store.put(item)
    return response(201, item)


def get_customer(store, customer_id):
    item = store.get(customer_id)
    if item is None:
        return response(404, {"message": f"Customer not found: {customer_id}"})
    return response(200, item)


def list_customers(store):
    return response(200, store.all())


def update_customer(store, customer_id, payload):
    if not store.exists(customer_id):
        return response(404, {"message": f"Customer not found: {customer_id}"})

    missing = validate_payload(payload)
    if missing:
        return response(400, {"message": f"Missing required fields: {', '.join(missing)}"})

    item = store.get(customer_id)
    item["name"] = payload["name"]
    item["email"] = payload["email"]
    if payload.get("phone") is not None:
        item["phone"] = payload["phone"]
    store.put(item)
    return response(200, item)


def delete_customer(store, customer_id):
    if not store.exists(customer_id):
        return response(404, {"message": f"Customer not found: {customer_id}"})
    store.delete(customer_id)
    return response(200, {"message": f"Customer deleted: {customer_id}"})


# ─── Authorizer IAM policy (mirrors the TOKEN Lambda Authorizer) ──────────────
def build_authorizer_policy(method_arn, principal_id, groups, admin_group="admin"):
    """Build the IAM policy document returned by the authorizer.

    Read methods are always allowed for authenticated users. Write methods
    (POST, PUT, DELETE) are only allowed for members of ``admin_group``;
    non-admins get explicit Deny statements for each write method.
    """
    arn_parts = method_arn.split(":")
    region = arn_parts[3]
    account = arn_parts[4]
    api_id, stage, *_ = arn_parts[5].split("/")
    base_arn = f"arn:aws:execute-api:{region}:{account}:{api_id}/{stage}/*"

    is_admin = admin_group in (groups or [])

    statements = [
        {"Action": "execute-api:Invoke", "Effect": "Allow", "Resource": base_arn}
    ]

    if not is_admin:
        for method in WRITE_METHODS:
            statements.append(
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Deny",
                    "Resource": f"arn:aws:execute-api:{region}:{account}:{api_id}/{stage}/{method}/*",
                }
            )

    return {
        "principalId": principal_id,
        "policyDocument": {"Version": "2012-10-17", "Statement": statements},
    }


def authorize_token(token):
    """Mimic the authorizer's token presence check.

    Raises ``Exception('Unauthorized')`` for a missing/blank token (which the
    real authorizer uses to trigger an HTTP 401), after stripping an optional
    ``Bearer`` prefix.
    """
    token = token or ""
    if token.lower().startswith("bearer "):
        token = token[7:]
    if not token.strip():
        raise Exception("Unauthorized")
    return token.strip()
