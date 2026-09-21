# Copyright AnyCompany
"""
Integration tests for the Customer Management API.

Prerequisites (set as environment variables before running):
  API_URL      - Base URL of the deployed API Gateway stage (e.g. https://abc.execute-api.us-east-1.amazonaws.com/dev)
  ADMIN_TOKEN  - Valid JWT token for a user in the admin Cognito group
  READER_TOKEN - Valid JWT token for a non-admin user

Run with:
  pytest tests/integration/ -v
"""

import os
import uuid
import pytest
import requests

API_URL      = os.environ.get("API_URL", "").rstrip("/")
ADMIN_TOKEN  = os.environ.get("ADMIN_TOKEN", "")
READER_TOKEN = os.environ.get("READER_TOKEN", "")


def admin_headers():
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


def reader_headers():
    return {"Authorization": f"Bearer {READER_TOKEN}"}


@pytest.fixture(scope="module")
def created_customer():
    """Create a customer before tests that need one and delete it after."""
    payload = {
        "name": f"Test User {uuid.uuid4()}",
        "email": f"test+{uuid.uuid4()}@example.com",
        "phone": "+15550001234",
    }
    resp = requests.post(f"{API_URL}/customers", json=payload, headers=admin_headers())
    assert resp.status_code == 201, f"Setup failed: {resp.text}"
    customer = resp.json()
    yield customer
    # Cleanup
    requests.delete(f"{API_URL}/customers/{customer['customerId']}", headers=admin_headers())


class TestAuthentication:
    def test_no_token_returns_401(self):
        resp = requests.get(f"{API_URL}/customers")
        assert resp.status_code == 401

    def test_no_token_on_post_returns_401(self):
        resp = requests.post(f"{API_URL}/customers", json={"name": "x", "email": "x@x.com"})
        assert resp.status_code == 401

    def test_non_admin_post_returns_403(self):
        resp = requests.post(
            f"{API_URL}/customers",
            json={"name": "x", "email": "x@x.com"},
            headers=reader_headers(),
        )
        assert resp.status_code == 403

    def test_non_admin_put_returns_403(self, created_customer):
        cid = created_customer["customerId"]
        resp = requests.put(
            f"{API_URL}/customers/{cid}",
            json={"name": "New Name"},
            headers=reader_headers(),
        )
        assert resp.status_code == 403

    def test_non_admin_delete_returns_403(self, created_customer):
        cid = created_customer["customerId"]
        resp = requests.delete(f"{API_URL}/customers/{cid}", headers=reader_headers())
        assert resp.status_code == 403


class TestCreateCustomer:
    def test_admin_create_returns_201(self):
        payload = {"name": "Jane Smith", "email": "jane@example.com", "phone": "+15550001234"}
        resp = requests.post(f"{API_URL}/customers", json=payload, headers=admin_headers())
        assert resp.status_code == 201
        body = resp.json()
        assert "customerId" in body
        assert body["name"] == "Jane Smith"
        assert body["email"] == "jane@example.com"
        # Cleanup
        requests.delete(f"{API_URL}/customers/{body['customerId']}", headers=admin_headers())

    def test_create_missing_name_returns_400(self):
        resp = requests.post(
            f"{API_URL}/customers",
            json={"email": "noname@example.com"},
            headers=admin_headers(),
        )
        assert resp.status_code == 400

    def test_create_missing_email_returns_400(self):
        resp = requests.post(
            f"{API_URL}/customers",
            json={"name": "No Email"},
            headers=admin_headers(),
        )
        assert resp.status_code == 400


class TestRetrieveCustomer:
    def test_reader_get_existing_returns_200(self, created_customer):
        cid = created_customer["customerId"]
        resp = requests.get(f"{API_URL}/customers/{cid}", headers=reader_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert body["customerId"] == cid

    def test_get_nonexistent_returns_404(self):
        fake_id = str(uuid.uuid4())
        resp = requests.get(f"{API_URL}/customers/{fake_id}", headers=reader_headers())
        assert resp.status_code == 404

    def test_get_no_token_returns_401(self, created_customer):
        cid = created_customer["customerId"]
        resp = requests.get(f"{API_URL}/customers/{cid}")
        assert resp.status_code == 401


class TestListCustomers:
    def test_reader_list_returns_200(self, created_customer):
        resp = requests.get(f"{API_URL}/customers", headers=reader_headers())
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        ids = [c["customerId"] for c in body]
        assert created_customer["customerId"] in ids

    def test_list_no_token_returns_401(self):
        resp = requests.get(f"{API_URL}/customers")
        assert resp.status_code == 401


class TestUpdateCustomer:
    def test_admin_update_returns_200(self, created_customer):
        cid = created_customer["customerId"]
        new_name = f"Updated {uuid.uuid4()}"
        resp = requests.put(
            f"{API_URL}/customers/{cid}",
            json={"name": new_name},
            headers=admin_headers(),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == new_name

    def test_update_reflects_on_get(self, created_customer):
        cid = created_customer["customerId"]
        new_email = f"updated+{uuid.uuid4()}@example.com"
        requests.put(
            f"{API_URL}/customers/{cid}",
            json={"email": new_email},
            headers=admin_headers(),
        )
        get_resp = requests.get(f"{API_URL}/customers/{cid}", headers=reader_headers())
        assert get_resp.json()["email"] == new_email

    def test_update_nonexistent_returns_404(self):
        fake_id = str(uuid.uuid4())
        resp = requests.put(
            f"{API_URL}/customers/{fake_id}",
            json={"name": "Ghost"},
            headers=admin_headers(),
        )
        assert resp.status_code == 404


class TestDeleteCustomer:
    def test_admin_delete_returns_200(self):
        payload = {"name": "To Delete", "email": f"del+{uuid.uuid4()}@example.com"}
        create_resp = requests.post(f"{API_URL}/customers", json=payload, headers=admin_headers())
        assert create_resp.status_code == 201
        cid = create_resp.json()["customerId"]

        del_resp = requests.delete(f"{API_URL}/customers/{cid}", headers=admin_headers())
        assert del_resp.status_code == 200

        get_resp = requests.get(f"{API_URL}/customers/{cid}", headers=reader_headers())
        assert get_resp.status_code == 404

    def test_delete_nonexistent_returns_404(self):
        fake_id = str(uuid.uuid4())
        resp = requests.delete(f"{API_URL}/customers/{fake_id}", headers=admin_headers())
        assert resp.status_code == 404
