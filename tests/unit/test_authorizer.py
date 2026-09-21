# Copyright AnyCompany

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src/authorizer"))

SAMPLE_METHOD_ARN = "arn:aws:execute-api:us-east-1:123456789:abc123/dev/GET/customers"

ADMIN_CLAIMS = {
    "sub": "user-123",
    "cognito:groups": ["admin"],
    "aud": "test-client-id",
}

NON_ADMIN_CLAIMS = {
    "sub": "user-456",
    "cognito:groups": ["readers"],
    "aud": "test-client-id",
}


def _get_lambda_function():
    """Import and return the authorizer lambda_function module.

    Uses spec_from_file_location with an explicit path so the authorizer
    module is always loaded from src/authorizer/, regardless of which
    lambda_function may already be cached in sys.modules by other test files.
    """
    import importlib.util

    # Remove any previously cached lambda_function (could be from src/customers)
    sys.modules.pop("lambda_function", None)

    spec = importlib.util.spec_from_file_location(
        "lambda_function",
        os.path.join(os.path.dirname(__file__), "../../src/authorizer/lambda_function.py"),
    )
    lf = importlib.util.module_from_spec(spec)
    sys.modules["lambda_function"] = lf
    spec.loader.exec_module(lf)
    return lf


class TestAuthorizerLambdaHandler(unittest.TestCase):

    def _make_event(self, token):
        return {
            "type": "TOKEN",
            "authorizationToken": token,
            "methodArn": SAMPLE_METHOD_ARN,
        }

    def test_valid_admin_token_returns_allow_all(self):
        """Admin token: Allow on base_arn, no Deny statements."""
        lf = _get_lambda_function()
        with patch.object(lf, "decode_token", return_value=ADMIN_CLAIMS):
            result = lf.lambda_handler(self._make_event("Bearer valid-token"), None)

        self.assertEqual(result["principalId"], "user-123")
        statements = result["policyDocument"]["Statement"]
        effects = [s["Effect"] for s in statements]
        self.assertIn("Allow", effects)
        self.assertNotIn("Deny", effects)

    def test_valid_non_admin_token_returns_allow_and_deny(self):
        """Non-admin token: Allow on base_arn + Deny for POST/PUT/DELETE."""
        lf = _get_lambda_function()
        with patch.object(lf, "decode_token", return_value=NON_ADMIN_CLAIMS):
            result = lf.lambda_handler(self._make_event("Bearer valid-token"), None)

        self.assertEqual(result["principalId"], "user-456")
        statements = result["policyDocument"]["Statement"]
        allow_stmts = [s for s in statements if s["Effect"] == "Allow"]
        deny_stmts = [s for s in statements if s["Effect"] == "Deny"]
        self.assertEqual(len(allow_stmts), 1)
        self.assertEqual(len(deny_stmts), 3)
        deny_resources = [s["Resource"] for s in deny_stmts]
        self.assertTrue(any("POST" in r for r in deny_resources))
        self.assertTrue(any("PUT" in r for r in deny_resources))
        self.assertTrue(any("DELETE" in r for r in deny_resources))

    def test_missing_token_raises_unauthorized(self):
        """Empty token raises Exception('Unauthorized')."""
        lf = _get_lambda_function()
        with self.assertRaises(Exception) as ctx:
            lf.lambda_handler(self._make_event(""), None)
        self.assertEqual(str(ctx.exception), "Unauthorized")

    def test_decode_token_failure_propagates_unauthorized(self):
        """If decode_token raises Unauthorized, lambda_handler re-raises it."""
        lf = _get_lambda_function()
        with patch.object(lf, "decode_token", side_effect=Exception("Unauthorized")):
            with self.assertRaises(Exception) as ctx:
                lf.lambda_handler(self._make_event("Bearer bad-token"), None)
        self.assertEqual(str(ctx.exception), "Unauthorized")

    def test_bearer_prefix_stripped(self):
        """Bearer prefix is stripped before passing to decode_token."""
        captured = {}
        lf = _get_lambda_function()

        def fake_decode(token):
            captured["token"] = token
            return ADMIN_CLAIMS

        with patch.object(lf, "decode_token", side_effect=fake_decode):
            lf.lambda_handler(self._make_event("Bearer actual-token"), None)

        self.assertEqual(captured["token"], "actual-token")


class TestDecodeToken(unittest.TestCase):

    def test_missing_kid_raises_unauthorized(self):
        """No matching key in JWKS raises Unauthorized."""
        fake_jwks = {"keys": [{"kid": "other-kid", "kty": "RSA"}]}
        lf = _get_lambda_function()
        with patch.object(lf, "get_jwks", return_value=fake_jwks):
            with patch.object(lf.jwt, "get_unverified_header", return_value={"kid": "my-kid"}):
                with self.assertRaises(Exception) as ctx:
                    lf.decode_token("some-token")
        self.assertEqual(str(ctx.exception), "Unauthorized")


if __name__ == "__main__":
    unittest.main()
