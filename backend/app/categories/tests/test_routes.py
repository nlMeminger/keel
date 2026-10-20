import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.accounts.models import Account
from app.categories.models import Category
from app.transactions.models import Transaction


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_system_categories_are_listed_and_include_transfer(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("category-lister@example.com")
    resp = client.get(
        "/api/v1/categories", params={"scope": "system"}, headers=_auth_headers(token)
    )
    names = {row["primary_category"] for row in resp.json()["data"]}
    assert "Transfer" in names
    assert all(row["owner_id"] is None for row in resp.json()["data"])


def test_create_custom_category(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, user_id = register_and_login("category-creator@example.com")
    resp = client.post(
        "/api/v1/categories",
        json={"primary_category": "Hobbies", "icon": "paint"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["primary_category"] == "Hobbies"
    assert data["owner_id"] == str(user_id)


def test_scope_custom_excludes_system_categories(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("category-scoper@example.com")
    client.post(
        "/api/v1/categories", json={"primary_category": "My Thing"}, headers=_auth_headers(token)
    )
    resp = client.get(
        "/api/v1/categories", params={"scope": "custom"}, headers=_auth_headers(token)
    )
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["primary_category"] == "My Thing"


def test_patch_system_category_returns_403(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]], db: DbSession
) -> None:
    token, _user_id = register_and_login("category-patcher@example.com")
    transfer = db.scalar(select(Category).where(Category.primary_category == "Transfer"))
    assert transfer is not None

    resp = client.patch(
        f"/api/v1/categories/{transfer.id}",
        json={"primary_category": "Hacked"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 403


def test_delete_system_category_returns_403(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]], db: DbSession
) -> None:
    token, _user_id = register_and_login("category-sys-deleter@example.com")
    transfer = db.scalar(select(Category).where(Category.primary_category == "Transfer"))
    assert transfer is not None

    resp = client.delete(f"/api/v1/categories/{transfer.id}", headers=_auth_headers(token))
    assert resp.status_code == 403


def test_delete_category_referenced_by_transaction_returns_409_unless_reassigned(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]], db: DbSession
) -> None:
    token, user_id = register_and_login("category-deleter@example.com")
    create_resp = client.post(
        "/api/v1/categories", json={"primary_category": "Groceries"}, headers=_auth_headers(token)
    )
    category_id = uuid.UUID(create_resp.json()["data"]["id"])

    other_resp = client.post(
        "/api/v1/categories", json={"primary_category": "Food"}, headers=_auth_headers(token)
    )
    other_category_id = other_resp.json()["data"]["id"]

    account = Account(
        user_id=user_id, name="Checking", account_type="checking", balance=Decimal("0")
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    txn = Transaction(
        user_id=user_id,
        account_id=account.id,
        category_id=category_id,
        amount=Decimal("-10.00"),
        description="Groceries run",
        date=date(2026, 1, 1),
    )
    db.add(txn)
    db.commit()

    # No reassign_to supplied -> 409, category and reference both untouched.
    conflict_resp = client.delete(f"/api/v1/categories/{category_id}", headers=_auth_headers(token))
    assert conflict_resp.status_code == 409

    # Supplying reassign_to re-points the transaction and lets the delete succeed.
    ok_resp = client.delete(
        f"/api/v1/categories/{category_id}",
        params={"reassign_to": other_category_id},
        headers=_auth_headers(token),
    )
    assert ok_resp.status_code == 204

    db.refresh(txn)
    assert str(txn.category_id) == other_category_id


def test_delete_custom_category_with_no_references_succeeds(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("category-free-deleter@example.com")
    create_resp = client.post(
        "/api/v1/categories", json={"primary_category": "Unused"}, headers=_auth_headers(token)
    )
    category_id = create_resp.json()["data"]["id"]

    resp = client.delete(f"/api/v1/categories/{category_id}", headers=_auth_headers(token))
    assert resp.status_code == 204


def test_categories_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/categories").status_code == 401


def test_nonexistent_category_returns_404(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("category-nobody@example.com")
    resp = client.patch(
        f"/api/v1/categories/{uuid.uuid4()}",
        json={"primary_category": "x"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 404


def test_a_second_users_token_cannot_modify_the_first_users_custom_category(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("category-owner@example.com")
    create_resp = client.post(
        "/api/v1/categories",
        json={"primary_category": "Private"},
        headers=_auth_headers(owner_token),
    )
    category_id = create_resp.json()["data"]["id"]

    intruder_token, _intruder_id = register_and_login("category-intruder@example.com")
    intruder_headers = _auth_headers(intruder_token)

    assert (
        client.patch(
            f"/api/v1/categories/{category_id}",
            json={"primary_category": "Stolen"},
            headers=intruder_headers,
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/categories/{category_id}", headers=intruder_headers).status_code
        == 404
    )
