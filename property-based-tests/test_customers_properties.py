# Copyright AnyCompany
"""Property-based tests for the Customers Lambda domain logic.

Each test maps to a formal property declared in the design document's
"Correctness Properties" section
(.kiro/specs/customer-management-platform/design.md).

These are property-based tests (Hypothesis): instead of fixed example inputs
like the tests in ``tests/``, they assert invariants that must hold for *all*
generated inputs.
"""

import json

from hypothesis import given, settings
from hypothesis import strategies as st

import customer_logic as cl
from strategies import invalid_payload, valid_payload


def _fresh_store():
    return cl.CustomerStore()


# ─── Property 1: Customer ID is always a UUID v4 ──────────────────────────────
@given(payload=valid_payload())
def test_property1_created_id_is_uuid_v4(payload):
    resp = cl.create_customer(_fresh_store(), payload)
    assert resp["statusCode"] == 201
    body = json.loads(resp["body"])
    assert cl.UUID_V4_RE.match(body["customerId"]), body["customerId"]


# ─── Property 2: Missing required fields always returns HTTP 400 ──────────────
@given(payload=invalid_payload())
def test_property2_invalid_create_returns_400(payload):
    resp = cl.create_customer(_fresh_store(), payload)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["message"].strip() != ""


@given(payload=invalid_payload())
def test_property2_invalid_update_returns_400(payload):
    # Seed an existing customer so the handler reaches payload validation
    # rather than short-circuiting on a 404.
    store = _fresh_store()
    created = json.loads(cl.create_customer(store, {"name": "Seed", "email": "seed@x.com"})["body"])
    resp = cl.update_customer(store, created["customerId"], payload)
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["message"].strip() != ""


# ─── Property 3: Create-then-retrieve round trip preserves data ───────────────
@given(payload=valid_payload())
def test_property3_create_then_get_roundtrip(payload):
    store = _fresh_store()
    created = json.loads(cl.create_customer(store, payload)["body"])

    resp = cl.get_customer(store, created["customerId"])
    assert resp["statusCode"] == 200
    fetched = json.loads(resp["body"])

    assert fetched["name"] == payload["name"]
    assert fetched["email"] == payload["email"]
    if payload.get("phone") is not None:
        assert fetched["phone"] == payload["phone"]


# ─── Property 4: Update-then-retrieve round trip reflects new values ──────────
@given(initial=valid_payload(), update=valid_payload())
def test_property4_update_then_get_reflects_update(initial, update):
    store = _fresh_store()
    created = json.loads(cl.create_customer(store, initial)["body"])
    cid = created["customerId"]

    upd_resp = cl.update_customer(store, cid, update)
    assert upd_resp["statusCode"] == 200

    fetched = json.loads(cl.get_customer(store, cid)["body"])
    assert fetched["name"] == update["name"]
    assert fetched["email"] == update["email"]


# ─── Property 5: Delete makes record unretrievable ────────────────────────────
@given(payload=valid_payload())
def test_property5_delete_makes_unretrievable(payload):
    store = _fresh_store()
    created = json.loads(cl.create_customer(store, payload)["body"])
    cid = created["customerId"]

    del_resp = cl.delete_customer(store, cid)
    assert del_resp["statusCode"] == 200

    assert cl.get_customer(store, cid)["statusCode"] == 404


# ─── Property 6: Non-existent customer ID always returns HTTP 404 ─────────────
@given(fake_id=st.uuids().map(str), payload=valid_payload())
def test_property6_get_update_delete_unknown_returns_404(fake_id, payload):
    store = _fresh_store()  # empty: fake_id never created

    get_resp = cl.get_customer(store, fake_id)
    upd_resp = cl.update_customer(store, fake_id, payload)
    del_resp = cl.delete_customer(store, fake_id)

    for resp in (get_resp, upd_resp, del_resp):
        assert resp["statusCode"] == 404
        assert json.loads(resp["body"])["message"].strip() != ""


# ─── Property 7: List returns all created customers ───────────────────────────
@given(payloads=st.lists(valid_payload(), min_size=0, max_size=15))
@settings(max_examples=100)
def test_property7_list_returns_all_created(payloads):
    store = _fresh_store()
    created_ids = set()
    for payload in payloads:
        created = json.loads(cl.create_customer(store, payload)["body"])
        created_ids.add(created["customerId"])

    resp = cl.list_customers(store)
    assert resp["statusCode"] == 200
    listed = json.loads(resp["body"])
    listed_ids = {item["customerId"] for item in listed}

    assert created_ids == listed_ids
    assert len(listed) == len(created_ids)
