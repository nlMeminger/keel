import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session as OrmSession

from app.auth.models import User
from app.banks import seed as banks_seed
from app.banks.models import Institution
from app.categories.models import Category
from app.categories.seed import SYSTEM_CATEGORIES


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_admin(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
    email: str,
) -> str:
    token, user_id = register_and_login(email)
    user = db.get(User, user_id)
    assert user is not None
    user.role = "admin"
    db.commit()
    return token


def test_seed_routes_require_admin(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _ = register_and_login("plain-seed@example.com")
    assert (
        client.post("/api/v1/admin/categories/seed", headers=_auth_headers(token)).status_code
        == 403
    )
    assert client.post("/api/v1/admin/banks/seed", headers=_auth_headers(token)).status_code == 403


def test_categories_seed_is_idempotent(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    admin_token = _make_admin(client, register_and_login, db, "admin-cat-seed@example.com")
    # conftest's autouse _reset_schema fixture already seeds these for every test — clear
    # them first so this test can observe the "nothing existed yet" creation path too.
    db.execute(delete(Category).where(Category.owner_id.is_(None)))
    db.commit()

    first = client.post("/api/v1/admin/categories/seed", headers=_auth_headers(admin_token))
    assert first.status_code == 200
    assert first.json()["data"]["created"] == len(SYSTEM_CATEGORIES)

    second = client.post("/api/v1/admin/categories/seed", headers=_auth_headers(admin_token))
    assert second.status_code == 200
    assert second.json()["data"]["created"] == 0

    count = db.scalar(select(func.count()).select_from(Category).where(Category.owner_id.is_(None)))
    assert count == len(SYSTEM_CATEGORIES)


class _FakeInstitution:
    def __init__(self, institution_id: str, name: str, logo: str | None = None) -> None:
        self.institution_id = institution_id
        self.name = name
        self.logo = logo


class _FakeInstitutionsGetResponse:
    def __init__(self, institutions: list[_FakeInstitution]) -> None:
        self.institutions = institutions


class _FakeClient:
    def __init__(self, institutions: list[_FakeInstitution]) -> None:
        self._institutions = institutions

    def institutions_get(self, request: object) -> _FakeInstitutionsGetResponse:
        return _FakeInstitutionsGetResponse(self._institutions)


def test_institutions_seed_creates_then_updates_idempotently(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_token = _make_admin(client, register_and_login, db, "admin-inst-seed@example.com")

    monkeypatch.setattr(
        banks_seed,
        "get_plaid_client",
        lambda: _FakeClient([_FakeInstitution("ins_1", "First Bank", "http://logo")]),
    )
    first = client.post("/api/v1/admin/banks/seed", headers=_auth_headers(admin_token))
    assert first.status_code == 200
    assert first.json()["data"] == {"created": 1, "updated": 0}

    row = db.scalar(select(Institution).where(Institution.plaid_institution_id == "ins_1"))
    assert row is not None
    assert row.name == "First Bank"

    monkeypatch.setattr(
        banks_seed,
        "get_plaid_client",
        lambda: _FakeClient([_FakeInstitution("ins_1", "First Bank Renamed", "http://logo2")]),
    )
    second = client.post("/api/v1/admin/banks/seed", headers=_auth_headers(admin_token))
    assert second.status_code == 200
    assert second.json()["data"] == {"created": 0, "updated": 1}

    db.refresh(row)
    assert row.name == "First Bank Renamed"

    total = db.scalar(select(func.count()).select_from(Institution))
    assert total == 1
