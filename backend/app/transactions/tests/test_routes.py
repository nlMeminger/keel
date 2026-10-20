import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_account(client: TestClient, token: str, name: str = "Checking") -> str:
    resp = client.post(
        "/api/v1/accounts",
        json={"name": name, "account_type": "checking", "balance": "0"},
        headers=_auth_headers(token),
    )
    return str(resp.json()["data"]["id"])


def test_create_and_get_transaction_preserves_amount_sign(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("txn-creator@example.com")
    account_id = _create_account(client, token)

    income_resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "amount": "500.00",
            "description": "Paycheck",
            "date": "2026-01-15",
        },
        headers=_auth_headers(token),
    )
    assert income_resp.status_code == 201
    assert income_resp.json()["data"]["amount"] == "500.00"

    expense_resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "amount": "-42.50",
            "description": "Groceries",
            "date": "2026-01-16",
        },
        headers=_auth_headers(token),
    )
    assert expense_resp.json()["data"]["amount"] == "-42.50"

    get_resp = client.get(
        f"/api/v1/transactions/{expense_resp.json()['data']['id']}", headers=_auth_headers(token)
    )
    assert get_resp.json()["data"]["description"] == "Groceries"


def test_combined_filters_return_exactly_the_expected_subset(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("txn-filterer@example.com")
    account_a = _create_account(client, token, "A")
    account_b = _create_account(client, token, "B")

    def add(account_id: str, amount: str, desc: str, txn_date: str) -> None:
        resp = client.post(
            "/api/v1/transactions",
            json={
                "account_id": account_id,
                "amount": amount,
                "description": desc,
                "date": txn_date,
            },
            headers=_auth_headers(token),
        )
        assert resp.status_code == 201

    # Matches: account_a, within date range, within amount range.
    add(account_a, "-50.00", "Match 1", "2026-02-10")
    add(account_a, "-75.00", "Match 2", "2026-02-15")
    # Non-matches: wrong account, outside date range, outside amount range.
    add(account_b, "-60.00", "Wrong account", "2026-02-10")
    add(account_a, "-60.00", "Wrong date", "2026-03-01")
    add(account_a, "-500.00", "Wrong amount", "2026-02-10")

    resp = client.get(
        "/api/v1/transactions",
        params={
            "account_id": account_a,
            "date_from": "2026-02-01",
            "date_to": "2026-02-28",
            "amount_min": "-100",
            "amount_max": "0",
        },
        headers=_auth_headers(token),
    )
    descriptions = {row["description"] for row in resp.json()["data"]}
    assert descriptions == {"Match 1", "Match 2"}


def test_pagination_defaults_and_max_enforced(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("txn-paginator@example.com")
    account_id = _create_account(client, token)
    for i in range(3):
        client.post(
            "/api/v1/transactions",
            json={
                "account_id": account_id,
                "amount": "-1.00",
                "description": f"Item {i}",
                "date": "2026-01-01",
            },
            headers=_auth_headers(token),
        )

    default_resp = client.get("/api/v1/transactions", headers=_auth_headers(token))
    assert default_resp.json()["pagination"]["page_size"] == 25

    too_big_resp = client.get(
        "/api/v1/transactions", params={"page_size": 201}, headers=_auth_headers(token)
    )
    assert too_big_resp.status_code == 422

    bad_page_resp = client.get(
        "/api/v1/transactions", params={"page": 0}, headers=_auth_headers(token)
    )
    assert bad_page_resp.status_code == 422


def test_description_free_text_filter(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("txn-desc-filterer@example.com")
    account_id = _create_account(client, token)
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "amount": "-1",
            "description": "Coffee Shop",
            "date": "2026-01-01",
        },
        headers=_auth_headers(token),
    )
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "amount": "-1",
            "description": "Gas Station",
            "date": "2026-01-01",
        },
        headers=_auth_headers(token),
    )

    resp = client.get(
        "/api/v1/transactions", params={"description": "coffee"}, headers=_auth_headers(token)
    )
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["description"] == "Coffee Shop"


def test_merchant_free_text_filter(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("txn-merchant-filterer@example.com")
    account_id = _create_account(client, token)
    merchant_resp = client.post(
        "/api/v1/merchants", json={"name": "Big Grocery Chain"}, headers=_auth_headers(token)
    )
    merchant_id = merchant_resp.json()["data"]["id"]
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "merchant_id": merchant_id,
            "amount": "-1",
            "description": "whatever",
            "date": "2026-01-01",
        },
        headers=_auth_headers(token),
    )
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "amount": "-1",
            "description": "no merchant here",
            "date": "2026-01-01",
        },
        headers=_auth_headers(token),
    )

    resp = client.get(
        "/api/v1/transactions", params={"merchant": "grocery"}, headers=_auth_headers(token)
    )
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["merchant_id"] == merchant_id


def test_update_can_clear_category_to_null_vs_leave_untouched(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("txn-updater@example.com")
    account_id = _create_account(client, token)
    category_resp = client.post(
        "/api/v1/categories", json={"primary_category": "Food"}, headers=_auth_headers(token)
    )
    category_id = category_resp.json()["data"]["id"]

    create_resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "category_id": category_id,
            "amount": "-1",
            "description": "x",
            "date": "2026-01-01",
        },
        headers=_auth_headers(token),
    )
    txn_id = create_resp.json()["data"]["id"]

    # Omitting notes leaves category_id untouched.
    patch1 = client.patch(
        f"/api/v1/transactions/{txn_id}", json={"notes": "a note"}, headers=_auth_headers(token)
    )
    assert patch1.json()["data"]["category_id"] == category_id
    assert patch1.json()["data"]["notes"] == "a note"

    # Explicit null clears it (uncategorize).
    patch2 = client.patch(
        f"/api/v1/transactions/{txn_id}", json={"category_id": None}, headers=_auth_headers(token)
    )
    assert patch2.json()["data"]["category_id"] is None
    assert patch2.json()["data"]["notes"] == "a note"


def test_create_rejects_another_users_category(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("txn-cat-owner@example.com")
    category_resp = client.post(
        "/api/v1/categories",
        json={"primary_category": "Private"},
        headers=_auth_headers(owner_token),
    )
    category_id = category_resp.json()["data"]["id"]

    intruder_token, _intruder_id = register_and_login("txn-cat-intruder@example.com")
    account_id = _create_account(client, intruder_token)

    resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "category_id": category_id,
            "amount": "-1",
            "description": "x",
            "date": "2026-01-01",
        },
        headers=_auth_headers(intruder_token),
    )
    assert resp.status_code == 404


def test_delete_transaction(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("txn-deleter@example.com")
    account_id = _create_account(client, token)
    create_resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "amount": "-1",
            "description": "temp",
            "date": "2026-01-01",
        },
        headers=_auth_headers(token),
    )
    txn_id = create_resp.json()["data"]["id"]

    assert (
        client.delete(f"/api/v1/transactions/{txn_id}", headers=_auth_headers(token)).status_code
        == 204
    )
    assert (
        client.get(f"/api/v1/transactions/{txn_id}", headers=_auth_headers(token)).status_code
        == 404
    )


def test_transactions_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/transactions").status_code == 401


def test_nonexistent_transaction_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("txn-nobody@example.com")
    resp = client.get(f"/api/v1/transactions/{uuid.uuid4()}", headers=_auth_headers(token))
    assert resp.status_code == 404


def test_a_second_users_token_cannot_see_or_modify_the_first_users_transaction(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("txn-owner@example.com")
    account_id = _create_account(client, owner_token)
    create_resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "amount": "-1",
            "description": "private",
            "date": "2026-01-01",
        },
        headers=_auth_headers(owner_token),
    )
    txn_id = create_resp.json()["data"]["id"]

    intruder_token, _intruder_id = register_and_login("txn-intruder@example.com")
    intruder_headers = _auth_headers(intruder_token)

    assert client.get(f"/api/v1/transactions/{txn_id}", headers=intruder_headers).status_code == 404
    assert (
        client.patch(
            f"/api/v1/transactions/{txn_id}", json={"notes": "stolen"}, headers=intruder_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/transactions/{txn_id}", headers=intruder_headers).status_code == 404
    )
