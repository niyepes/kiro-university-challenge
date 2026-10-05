# Copyright AnyCompany
"""Property-based tests for the Authorizer Lambda domain logic.

Maps to Properties 8 and 9 of the design document's "Correctness Properties"
section (.kiro/specs/customer-management-platform/design.md).
"""

from hypothesis import given
from hypothesis import strategies as st

import customer_logic as cl
from strategies import group_lists, method_arns, principal_ids

ADMIN_GROUP = "admin"


# ─── Property 8: Invalid or missing token always returns 401 (Unauthorized) ───
@given(
    token=st.one_of(
        st.just(""),
        st.just("   "),
        st.just("Bearer "),
        st.just("Bearer    "),
        st.none(),
    )
)
def test_property8_missing_or_blank_token_raises_unauthorized(token):
    try:
        cl.authorize_token(token)
    except Exception as exc:  # noqa: BLE001 - we assert on the message
        assert str(exc) == "Unauthorized"
    else:
        raise AssertionError("Expected Unauthorized for missing/blank token")


@given(raw=st.text(min_size=1, max_size=40).filter(lambda s: s.strip() != ""))
def test_property8_nonblank_token_is_accepted_and_bearer_stripped(raw):
    # A non-blank token must NOT raise, and the Bearer prefix must be stripped.
    assert cl.authorize_token(raw) == raw.strip()
    assert cl.authorize_token(f"Bearer {raw}") == raw.strip()


# ─── Property 9: Non-admin token on write operations yields Deny ──────────────
@given(
    method_arn=method_arns,
    principal_id=principal_ids,
    groups=group_lists.filter(lambda g: ADMIN_GROUP not in g),
)
def test_property9_non_admin_gets_deny_on_writes(method_arn, principal_id, groups):
    policy = cl.build_authorizer_policy(method_arn, principal_id, groups, ADMIN_GROUP)
    statements = policy["policyDocument"]["Statement"]

    deny = [s for s in statements if s["Effect"] == "Deny"]
    allow = [s for s in statements if s["Effect"] == "Allow"]

    # Exactly one broad Allow (read access) and one Deny per write method.
    assert len(allow) == 1
    assert len(deny) == len(cl.WRITE_METHODS)

    deny_resources = " ".join(s["Resource"] for s in deny)
    for method in cl.WRITE_METHODS:
        assert f"/{method}/" in deny_resources

    assert policy["principalId"] == principal_id


# ─── Complement of Property 9: admin token gets no Deny statements ────────────
@given(
    method_arn=method_arns,
    principal_id=principal_ids,
    extra_groups=group_lists,
)
def test_property9_admin_gets_no_deny(method_arn, principal_id, extra_groups):
    groups = list(extra_groups) + [ADMIN_GROUP]
    policy = cl.build_authorizer_policy(method_arn, principal_id, groups, ADMIN_GROUP)
    statements = policy["policyDocument"]["Statement"]

    effects = [s["Effect"] for s in statements]
    assert "Allow" in effects
    assert "Deny" not in effects
