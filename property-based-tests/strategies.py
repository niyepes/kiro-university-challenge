# Copyright AnyCompany
"""Shared Hypothesis strategies for generating customer domain data."""

from hypothesis import strategies as st

# Non-blank text: at least one non-whitespace character so it passes validation.
non_blank_text = st.text(min_size=1, max_size=60).filter(lambda s: s.strip() != "")

# Optional phone: either absent (None) or an arbitrary short string.
optional_phone = st.one_of(st.none(), st.text(max_size=20))


def valid_payload():
    """A payload that always has non-blank name and email, plus optional phone."""
    return st.fixed_dictionaries(
        {
            "name": non_blank_text,
            "email": non_blank_text,
        }
    ).flatmap(
        lambda base: optional_phone.map(
            lambda phone: {**base, **({"phone": phone} if phone is not None else {})}
        )
    )


def invalid_payload():
    """A payload missing name, email, or both (or with blank values)."""
    blank_or_absent = st.one_of(st.none(), st.just(""), st.just("   "))

    def build(name, email, drop_name, drop_email):
        payload = {}
        if not drop_name:
            payload["name"] = name
        if not drop_email:
            payload["email"] = email
        return payload

    return st.builds(
        build,
        name=st.one_of(non_blank_text, blank_or_absent),
        email=st.one_of(non_blank_text, blank_or_absent),
        drop_name=st.booleans(),
        drop_email=st.booleans(),
    ).filter(
        # Keep only payloads that are genuinely invalid (at least one of
        # name/email missing or blank).
        lambda p: _is_missing(p, "name") or _is_missing(p, "email")
    )


def _is_missing(payload, field):
    value = payload.get(field)
    return value is None or (isinstance(value, str) and value.strip() == "")


# Cognito group lists.
group_names = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789-", min_size=1, max_size=15
)
group_lists = st.lists(group_names, max_size=5, unique=True)

# A method ARN like the one API Gateway passes to a TOKEN authorizer.
method_arns = st.builds(
    lambda region, account, api_id, stage, method, path: (
        f"arn:aws:execute-api:{region}:{account}:{api_id}/{stage}/{method}/{path}"
    ),
    region=st.sampled_from(["us-east-1", "us-west-2", "eu-west-1"]),
    account=st.text(alphabet="0123456789", min_size=12, max_size=12),
    api_id=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=6, max_size=10),
    stage=st.sampled_from(["dev", "prod", "staging"]),
    method=st.sampled_from(["GET", "POST", "PUT", "DELETE"]),
    path=st.sampled_from(["customers", "customers/123", "customers/search"]),
)

principal_ids = st.text(min_size=1, max_size=36)
