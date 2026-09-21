# Copyright AnyCompany

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure src/customers is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/customers"))

EVENTS_DIR = os.path.join(os.path.dirname(__file__), "events")


def load_event(filename):
    with open(os.path.join(EVENTS_DIR, filename)) as f:
        return json.load(f)


CUSTOMER_ID = "550e8400-e29b-41d4-a716-446655440000"

SAMPLE_ITEM = {
    "customerId": CUSTOMER_ID,
    "name": "Jane Doe",
    "email": "jane.doe@example.com",
    "phone": "+15559990000",
}


def make_table_mock():
    """Return a MagicMock that behaves like a DynamoDB Table."""
    table = MagicMock()
    return table


class TestCreateCustomer(unittest.TestCase):

    def _invoke(self, event, table_mock):
        with patch("boto3.resource") as mock_resource:
            mock_resource.return_value.Table.return_value = table_mock
            import importlib
            import lambda_function
            importlib.reload(lambda_function)
            return lambda_function.lambda_handler(event, None)

    def test_create_valid_payload_returns_201(self):
        table = make_table_mock()
        table.put_item.return_value = {}

        event = load_event("create_customer.json")
        resp = self._invoke(event, table)

        self.assertEqual(resp["statusCode"], 201)
        body = json.loads(resp["body"])
        self.assertIn("customerId", body)
        self.assertEqual(body["name"], "Jane Smith")
        self.assertEqual(body["email"], "jane@example.com")
        table.put_item.assert_called_once()

    def test_create_missing_name_returns_400(self):
        table = make_table_mock()
        event = {
            "httpMethod": "POST",
            "path": "/customers",
            "pathParameters": None,
            "body": json.dumps({"email": "test@example.com"}),
            "requestContext": {},
        }
        resp = self._invoke(event, table)
        self.assertEqual(resp["statusCode"], 400)
        body = json.loads(resp["body"])
        self.assertIn("message", body)

    def test_create_missing_email_returns_400(self):
        table = make_table_mock()
        event = {
            "httpMethod": "POST",
            "path": "/customers",
            "pathParameters": None,
            "body": json.dumps({"name": "Alice"}),
            "requestContext": {},
        }
        resp = self._invoke(event, table)
        self.assertEqual(resp["statusCode"], 400)
        body = json.loads(resp["body"])
        self.assertIn("message", body)


class TestGetCustomer(unittest.TestCase):

    def _invoke(self, event, table_mock):
        with patch("boto3.resource") as mock_resource:
            mock_resource.return_value.Table.return_value = table_mock
            import importlib
            import lambda_function
            importlib.reload(lambda_function)
            return lambda_function.lambda_handler(event, None)

    def test_get_existing_customer_returns_200(self):
        table = make_table_mock()
        table.get_item.return_value = {"Item": SAMPLE_ITEM}

        event = load_event("get_customer.json")
        resp = self._invoke(event, table)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["customerId"], CUSTOMER_ID)

    def test_get_nonexistent_customer_returns_404(self):
        table = make_table_mock()
        table.get_item.return_value = {}  # no "Item" key

        event = load_event("get_customer.json")
        resp = self._invoke(event, table)

        self.assertEqual(resp["statusCode"], 404)
        body = json.loads(resp["body"])
        self.assertIn("message", body)


class TestListCustomers(unittest.TestCase):

    def _invoke(self, event, table_mock):
        with patch("boto3.resource") as mock_resource:
            mock_resource.return_value.Table.return_value = table_mock
            import importlib
            import lambda_function
            importlib.reload(lambda_function)
            return lambda_function.lambda_handler(event, None)

    def test_list_returns_200_with_array(self):
        table = make_table_mock()
        table.scan.return_value = {"Items": [SAMPLE_ITEM]}

        event = load_event("list_customers.json")
        resp = self._invoke(event, table)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertIsInstance(body, list)
        self.assertEqual(len(body), 1)

    def test_list_empty_table_returns_200_empty_array(self):
        table = make_table_mock()
        table.scan.return_value = {"Items": []}

        event = load_event("list_customers.json")
        resp = self._invoke(event, table)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body, [])


class TestUpdateCustomer(unittest.TestCase):

    def _invoke(self, event, table_mock):
        with patch("boto3.resource") as mock_resource:
            mock_resource.return_value.Table.return_value = table_mock
            import importlib
            import lambda_function
            importlib.reload(lambda_function)
            return lambda_function.lambda_handler(event, None)

    def test_update_existing_customer_returns_200(self):
        table = make_table_mock()
        table.get_item.return_value = {"Item": SAMPLE_ITEM}
        updated = {**SAMPLE_ITEM, "name": "Jane Doe", "email": "jane.doe@example.com"}
        table.update_item.return_value = {"Attributes": updated}

        event = load_event("update_customer.json")
        resp = self._invoke(event, table)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertEqual(body["name"], "Jane Doe")

    def test_update_nonexistent_customer_returns_404(self):
        table = make_table_mock()
        table.get_item.return_value = {}  # no "Item" key

        event = load_event("update_customer.json")
        resp = self._invoke(event, table)

        self.assertEqual(resp["statusCode"], 404)
        body = json.loads(resp["body"])
        self.assertIn("message", body)


class TestDeleteCustomer(unittest.TestCase):

    def _invoke(self, event, table_mock):
        with patch("boto3.resource") as mock_resource:
            mock_resource.return_value.Table.return_value = table_mock
            import importlib
            import lambda_function
            importlib.reload(lambda_function)
            return lambda_function.lambda_handler(event, None)

    def test_delete_existing_customer_returns_200(self):
        table = make_table_mock()
        table.get_item.return_value = {"Item": SAMPLE_ITEM}
        table.delete_item.return_value = {}

        event = load_event("delete_customer.json")
        resp = self._invoke(event, table)

        self.assertEqual(resp["statusCode"], 200)
        body = json.loads(resp["body"])
        self.assertIn("message", body)
        table.delete_item.assert_called_once_with(Key={"customerId": CUSTOMER_ID})

    def test_delete_nonexistent_customer_returns_404(self):
        table = make_table_mock()
        table.get_item.return_value = {}  # no "Item" key

        event = load_event("delete_customer.json")
        resp = self._invoke(event, table)

        self.assertEqual(resp["statusCode"], 404)
        body = json.loads(resp["body"])
        self.assertIn("message", body)


class TestUnsupportedRoute(unittest.TestCase):

    def _invoke(self, event, table_mock):
        with patch("boto3.resource") as mock_resource:
            mock_resource.return_value.Table.return_value = table_mock
            import importlib
            import lambda_function
            importlib.reload(lambda_function)
            return lambda_function.lambda_handler(event, None)

    def test_unsupported_method_returns_400(self):
        table = make_table_mock()
        event = {
            "httpMethod": "PATCH",
            "path": "/customers",
            "pathParameters": None,
            "body": None,
            "requestContext": {},
        }
        resp = self._invoke(event, table)
        self.assertEqual(resp["statusCode"], 400)
        body = json.loads(resp["body"])
        self.assertIn("message", body)


if __name__ == "__main__":
    unittest.main()
