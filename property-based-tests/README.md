# Property-Based Tests

Property-based test suite for the Customer Management Platform, built with
[Hypothesis](https://hypothesis.readthedocs.io/).

Unlike the example-based tests under `tests/`, these tests assert **invariants**
that must hold for *all* automatically generated inputs. Each test maps to a
formal property from the "Correctness Properties" section of
`.kiro/specs/customer-management-platform/design.md`.

## Why a self-contained domain module?

The real Lambda source (`src/authorizer`, `src/customers`) is not present in the
repo yet, and the handlers depend on AWS (DynamoDB, Cognito). To keep these
tests runnable in isolation, `customer_logic.py` is a dependency-free reference
implementation of the same business rules (validation, CRUD responses, UUID v4
generation, and the authorizer IAM policy). When the real handlers land, the
tests can be repointed at them.

## Property coverage

| Test | Property |
| --- | --- |
| `test_property1_created_id_is_uuid_v4` | P1: customerId is always UUID v4 |
| `test_property2_invalid_*_returns_400` | P2: missing name/email -> 400 |
| `test_property3_create_then_get_roundtrip` | P3: create/retrieve preserves data |
| `test_property4_update_then_get_reflects_update` | P4: update/retrieve reflects values |
| `test_property5_delete_makes_unretrievable` | P5: delete -> 404 on retrieve |
| `test_property6_get_update_delete_unknown_returns_404` | P6: unknown id -> 404 |
| `test_property7_list_returns_all_created` | P7: list returns every created record |
| `test_property8_*` | P8: missing/invalid token -> Unauthorized (401) |
| `test_property9_*` | P9: non-admin writes -> Deny (403); admin -> no Deny |

## Setup

```bash
pip install -r property-based-tests/requirements.txt
```

## Run

```bash
pytest property-based-tests/
```
