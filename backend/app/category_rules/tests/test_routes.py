import uuid
from collections.abc import Callable
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.jobs.models import Job


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_account(client: TestClient, token: str, name: str = "Checking") -> str:
    resp = client.post(
        "/api/v1/accounts",
        json={"name": name, "account_type": "checking", "balance": "0"},
        headers=_auth_headers(token),
    )
    return str(resp.json()["data"]["id"])


def _create_category(client: TestClient, token: str, name: str) -> str:
    resp = client.post(
        "/api/v1/categories", json={"primary_category": name}, headers=_auth_headers(token)
    )
    return str(resp.json()["data"]["id"])


def _create_transaction(
    client: TestClient, token: str, account_id: str, description: str, amount: str
) -> str:
    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "amount": amount,
            "description": description,
            "date": date.today().isoformat(),
        },
        headers=_auth_headers(token),
    )
    return str(resp.json()["data"]["id"])


def test_create_and_list_rules(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("rule-create@example.com")
    category_id = _create_category(client, token, "Subscriptions")

    create_resp = client.post(
        "/api/v1/category-rules",
        json={"merchant_contains": "netflix", "category_id": category_id, "priority": 10},
        headers=_auth_headers(token),
    )
    assert create_resp.status_code == 201
    rule = create_resp.json()["data"]
    assert rule["merchant_contains"] == "netflix"
    assert rule["priority"] == 10
    assert rule["active"] is True

    list_resp = client.get("/api/v1/category-rules", headers=_auth_headers(token))
    assert len(list_resp.json()["data"]) == 1


def test_update_rule(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("rule-update@example.com")
    category_id = _create_category(client, token, "Subscriptions")
    rule_id = client.post(
        "/api/v1/category-rules",
        json={"merchant_contains": "netflix", "category_id": category_id},
        headers=_auth_headers(token),
    ).json()["data"]["id"]

    patch_resp = client.patch(
        f"/api/v1/category-rules/{rule_id}",
        json={"active": False, "priority": 5},
        headers=_auth_headers(token),
    )
    assert patch_resp.json()["data"]["active"] is False
    assert patch_resp.json()["data"]["priority"] == 5


def test_delete_rule(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("rule-delete@example.com")
    category_id = _create_category(client, token, "Subscriptions")
    rule_id = client.post(
        "/api/v1/category-rules",
        json={"merchant_contains": "netflix", "category_id": category_id},
        headers=_auth_headers(token),
    ).json()["data"]["id"]

    assert (
        client.delete(f"/api/v1/category-rules/{rule_id}", headers=_auth_headers(token)).status_code
        == 204
    )
    assert client.get("/api/v1/category-rules", headers=_auth_headers(token)).json()["data"] == []


def test_test_endpoint_returns_matches_without_applying(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("rule-test@example.com")
    account_id = _create_account(client, token)
    txn_id = _create_transaction(client, token, account_id, "NETFLIX.COM", "-15.99")
    _create_transaction(client, token, account_id, "Grocery store", "-40.00")

    test_resp = client.post(
        "/api/v1/category-rules/test",
        json={"merchant_contains": "netflix"},
        headers=_auth_headers(token),
    )
    matches = test_resp.json()["data"]["matches"]
    assert len(matches) == 1
    assert matches[0]["id"] == txn_id

    # Dry run must not have written anything.
    txn_resp = client.get(f"/api/v1/transactions/{txn_id}", headers=_auth_headers(token))
    assert txn_resp.json()["data"]["category_id"] is None


def test_apply_categorizes_uncategorized_transactions_and_job_succeeds(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: DbSession,
) -> None:
    token, _user_id = register_and_login("rule-apply@example.com")
    account_id = _create_account(client, token)
    subscriptions = _create_category(client, token, "Subscriptions")
    client.post(
        "/api/v1/category-rules",
        json={"merchant_contains": "netflix", "category_id": subscriptions},
        headers=_auth_headers(token),
    )
    txn_id = _create_transaction(client, token, account_id, "NETFLIX.COM", "-15.99")
    other_txn_id = _create_transaction(client, token, account_id, "Grocery store", "-40.00")

    apply_resp = client.post("/api/v1/category-rules/apply", headers=_auth_headers(token))
    assert apply_resp.status_code == 202
    job_id = apply_resp.json()["data"]["job_id"]

    job_resp = client.get(f"/api/v1/sync/jobs/{job_id}", headers=_auth_headers(token))
    job = job_resp.json()["data"]
    assert job["status"] == "succeeded"
    assert job["type"] == "category_rule_apply"

    # The polling contract's public shape has no `result` field (API_SPEC.md §16) — the match
    # count it mentions is only ever on the stored Job row itself.
    job_row = db.scalar(select(Job).where(Job.id == uuid.UUID(job_id)))
    assert job_row is not None
    assert job_row.result == {"matched_count": 1}

    matched_txn = client.get(f"/api/v1/transactions/{txn_id}", headers=_auth_headers(token))
    assert matched_txn.json()["data"]["category_id"] == subscriptions
    unmatched_txn = client.get(f"/api/v1/transactions/{other_txn_id}", headers=_auth_headers(token))
    assert unmatched_txn.json()["data"]["category_id"] is None


def test_apply_honors_priority_first_match_wins(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("rule-priority@example.com")
    account_id = _create_account(client, token)
    broad = _create_category(client, token, "Broad")
    narrow = _create_category(client, token, "Narrow")
    # Both rules match the same transaction; lower priority value should win.
    client.post(
        "/api/v1/category-rules",
        json={"merchant_contains": "netflix", "category_id": broad, "priority": 50},
        headers=_auth_headers(token),
    )
    client.post(
        "/api/v1/category-rules",
        json={"merchant_contains": "netflix", "category_id": narrow, "priority": 1},
        headers=_auth_headers(token),
    )
    txn_id = _create_transaction(client, token, account_id, "NETFLIX.COM", "-15.99")

    client.post("/api/v1/category-rules/apply", headers=_auth_headers(token))

    txn_resp = client.get(f"/api/v1/transactions/{txn_id}", headers=_auth_headers(token))
    assert txn_resp.json()["data"]["category_id"] == narrow


def test_apply_ignores_inactive_rules(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("rule-inactive@example.com")
    account_id = _create_account(client, token)
    category_id = _create_category(client, token, "Subscriptions")
    rule_id = client.post(
        "/api/v1/category-rules",
        json={"merchant_contains": "netflix", "category_id": category_id, "active": False},
        headers=_auth_headers(token),
    ).json()["data"]["id"]
    assert rule_id
    txn_id = _create_transaction(client, token, account_id, "NETFLIX.COM", "-15.99")

    client.post("/api/v1/category-rules/apply", headers=_auth_headers(token))

    txn_resp = client.get(f"/api/v1/transactions/{txn_id}", headers=_auth_headers(token))
    assert txn_resp.json()["data"]["category_id"] is None


def test_category_rules_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/category-rules").status_code == 401


def test_nonexistent_rule_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("rule-nobody@example.com")
    resp = client.patch(
        f"/api/v1/category-rules/{uuid.uuid4()}",
        json={"priority": 1},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 404


def test_a_second_users_token_cannot_see_or_modify_the_first_users_rule(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("rule-owner@example.com")
    category_id = _create_category(client, owner_token, "Subscriptions")
    rule_id = client.post(
        "/api/v1/category-rules",
        json={"merchant_contains": "netflix", "category_id": category_id},
        headers=_auth_headers(owner_token),
    ).json()["data"]["id"]

    intruder_token, _intruder_id = register_and_login("rule-intruder@example.com")
    intruder_headers = _auth_headers(intruder_token)

    assert (
        client.patch(
            f"/api/v1/category-rules/{rule_id}", json={"priority": 1}, headers=intruder_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/category-rules/{rule_id}", headers=intruder_headers).status_code
        == 404
    )
