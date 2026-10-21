import uuid
from collections.abc import Callable
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.accounts.models import Account
from app.transactions.models import Transaction


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_account(client: TestClient, token: str) -> str:
    resp = client.post(
        "/api/v1/accounts",
        json={"name": "Checking", "account_type": "checking", "balance": "0"},
        headers=_auth_headers(token),
    )
    return str(resp.json()["data"]["id"])


def _today_in_current_month(day: int = 5) -> str:
    today = date.today()
    return today.replace(day=min(day, 28)).isoformat()


def test_logging_a_transaction_updates_spend_so_far_without_manual_recompute(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("budget-spend@example.com")
    account_id = _create_account(client, token)
    category_resp = client.post(
        "/api/v1/categories", json={"primary_category": "Groceries"}, headers=_auth_headers(token)
    )
    category_id = category_resp.json()["data"]["id"]

    budget_resp = client.post(
        "/api/v1/budgets",
        json={
            "category_id": category_id,
            "amount_limit": "300.00",
            "start_date": _today_in_current_month(1),
        },
        headers=_auth_headers(token),
    )
    budget_id = budget_resp.json()["data"]["id"]
    assert budget_resp.json()["data"]["spend_so_far"] == "0"

    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "category_id": category_id,
            "amount": "-45.00",
            "description": "Groceries run",
            "date": _today_in_current_month(10),
        },
        headers=_auth_headers(token),
    )

    list_resp = client.get("/api/v1/budgets", headers=_auth_headers(token))
    budget_row = next(row for row in list_resp.json()["data"] if row["id"] == budget_id)
    assert budget_row["spend_so_far"] == "45.00"


def test_overall_budget_excludes_income_and_includes_all_categories(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("budget-overall@example.com")
    account_id = _create_account(client, token)

    budget_resp = client.post(
        "/api/v1/budgets",
        json={"amount_limit": "1000.00", "start_date": _today_in_current_month(1)},
        headers=_auth_headers(token),
    )
    budget_id = budget_resp.json()["data"]["id"]
    assert budget_resp.json()["data"]["category_id"] is None

    for amount in ("-20.00", "-30.00"):
        client.post(
            "/api/v1/transactions",
            json={
                "account_id": account_id,
                "amount": amount,
                "description": "spend",
                "date": _today_in_current_month(10),
            },
            headers=_auth_headers(token),
        )
    # Income (positive amount) must not count toward spend.
    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "amount": "500.00",
            "description": "paycheck",
            "date": _today_in_current_month(10),
        },
        headers=_auth_headers(token),
    )

    list_resp = client.get("/api/v1/budgets", headers=_auth_headers(token))
    budget_row = next(row for row in list_resp.json()["data"] if row["id"] == budget_id)
    assert budget_row["spend_so_far"] == "50.00"


def test_category_scoped_budget_ignores_other_categories(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("budget-scoped@example.com")
    account_id = _create_account(client, token)
    groceries = client.post(
        "/api/v1/categories", json={"primary_category": "Groceries"}, headers=_auth_headers(token)
    ).json()["data"]["id"]
    entertainment = client.post(
        "/api/v1/categories",
        json={"primary_category": "Entertainment"},
        headers=_auth_headers(token),
    ).json()["data"]["id"]

    budget_resp = client.post(
        "/api/v1/budgets",
        json={
            "category_id": groceries,
            "amount_limit": "100.00",
            "start_date": _today_in_current_month(1),
        },
        headers=_auth_headers(token),
    )
    budget_id = budget_resp.json()["data"]["id"]

    client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "category_id": entertainment,
            "amount": "-99.00",
            "description": "movie",
            "date": _today_in_current_month(10),
        },
        headers=_auth_headers(token),
    )

    list_resp = client.get("/api/v1/budgets", headers=_auth_headers(token))
    budget_row = next(row for row in list_resp.json()["data"] if row["id"] == budget_id)
    assert budget_row["spend_so_far"] == "0"


def test_transfer_transaction_drops_out_of_spend_so_far(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]], db: DbSession
) -> None:
    token, _user_id = register_and_login("budget-transfer@example.com")
    account_id = _create_account(client, token)

    budget_resp = client.post(
        "/api/v1/budgets",
        json={"amount_limit": "1000.00", "start_date": _today_in_current_month(1)},
        headers=_auth_headers(token),
    )
    budget_id = budget_resp.json()["data"]["id"]

    txn_resp = client.post(
        "/api/v1/transactions",
        json={
            "account_id": account_id,
            "amount": "-80.00",
            "description": "self transfer",
            "date": _today_in_current_month(10),
        },
        headers=_auth_headers(token),
    )
    txn_id = txn_resp.json()["data"]["id"]

    before_resp = client.get("/api/v1/budgets", headers=_auth_headers(token))
    before_row = next(row for row in before_resp.json()["data"] if row["id"] == budget_id)
    assert before_row["spend_so_far"] == "80.00"

    # Simulate 4.13's confirmation flipping is_transfer=true (transfer detection itself
    # isn't built yet — this test only verifies the spend computation honors the flag).
    account = db.scalar(select(Account).where(Account.id == uuid.UUID(account_id)))
    assert account is not None
    txn = db.scalar(select(Transaction).where(Transaction.id == uuid.UUID(txn_id)))
    assert txn is not None
    txn.is_transfer = True
    db.commit()

    after_resp = client.get("/api/v1/budgets", headers=_auth_headers(token))
    after_row = next(row for row in after_resp.json()["data"] if row["id"] == budget_id)
    assert after_row["spend_so_far"] == "0"


def test_update_budget_switch_category_to_overall(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("budget-switcher@example.com")
    category_id = client.post(
        "/api/v1/categories", json={"primary_category": "Food"}, headers=_auth_headers(token)
    ).json()["data"]["id"]
    create_resp = client.post(
        "/api/v1/budgets",
        json={
            "category_id": category_id,
            "amount_limit": "100.00",
            "start_date": _today_in_current_month(1),
        },
        headers=_auth_headers(token),
    )
    budget_id = create_resp.json()["data"]["id"]

    patch_resp = client.patch(
        f"/api/v1/budgets/{budget_id}", json={"category_id": None}, headers=_auth_headers(token)
    )
    assert patch_resp.json()["data"]["category_id"] is None


def test_delete_budget(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("budget-deleter@example.com")
    create_resp = client.post(
        "/api/v1/budgets",
        json={"amount_limit": "100.00", "start_date": _today_in_current_month(1)},
        headers=_auth_headers(token),
    )
    budget_id = create_resp.json()["data"]["id"]

    assert (
        client.delete(f"/api/v1/budgets/{budget_id}", headers=_auth_headers(token)).status_code
        == 204
    )
    assert client.get("/api/v1/budgets", headers=_auth_headers(token)).json()["data"] == []


def test_budgets_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/budgets").status_code == 401


def test_nonexistent_budget_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("budget-nobody@example.com")
    resp = client.patch(
        f"/api/v1/budgets/{uuid.uuid4()}", json={"amount_limit": "1"}, headers=_auth_headers(token)
    )
    assert resp.status_code == 404


def test_crossing_90_and_100_percent_creates_exactly_one_notification_each(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("budget-threshold@example.com")
    account_id = _create_account(client, token)
    client.post(
        "/api/v1/budgets",
        json={"amount_limit": "100.00", "start_date": _today_in_current_month(1)},
        headers=_auth_headers(token),
    )

    def _spend(amount: str) -> None:
        client.post(
            "/api/v1/transactions",
            json={
                "account_id": account_id,
                "amount": amount,
                "description": "spend",
                "date": _today_in_current_month(10),
            },
            headers=_auth_headers(token),
        )

    def _notification_types() -> list[str]:
        resp = client.get("/api/v1/notifications", headers=_auth_headers(token))
        return [row["type"] for row in resp.json()["data"]]

    _spend("-50.00")
    assert _notification_types() == []

    # Crosses 90% (now at 90/100).
    _spend("-40.00")
    assert _notification_types() == ["budget_threshold_90"]

    # Still above 90%, not yet 100% — must not duplicate the 90% notification.
    _spend("-5.00")
    assert _notification_types() == ["budget_threshold_90"]

    # Crosses 100%.
    _spend("-10.00")
    types = _notification_types()
    assert sorted(types) == ["budget_threshold_100", "budget_threshold_90"]

    # Further spend past 100% must not duplicate either notification again.
    _spend("-1.00")
    assert sorted(_notification_types()) == ["budget_threshold_100", "budget_threshold_90"]


def test_a_second_users_token_cannot_see_or_modify_the_first_users_budget(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("budget-owner@example.com")
    create_resp = client.post(
        "/api/v1/budgets",
        json={"amount_limit": "100.00", "start_date": _today_in_current_month(1)},
        headers=_auth_headers(owner_token),
    )
    budget_id = create_resp.json()["data"]["id"]

    intruder_token, _intruder_id = register_and_login("budget-intruder@example.com")
    intruder_headers = _auth_headers(intruder_token)

    assert (
        client.patch(
            f"/api/v1/budgets/{budget_id}", json={"amount_limit": "1"}, headers=intruder_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/budgets/{budget_id}", headers=intruder_headers).status_code == 404
    )
