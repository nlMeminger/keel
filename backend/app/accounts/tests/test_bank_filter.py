import uuid
from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.accounts.models import Account
from app.banks.models import Bank
from app.banks.models import PlaidItem as PlaidItemModel


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_bank(db: OrmSession, owner_id: uuid.UUID) -> Bank:
    item = PlaidItemModel(
        access_token="irrelevant-for-this-test",
        item_id=f"item-{uuid.uuid4()}",
        institution_id="ins_1",
        institution_name="Sandbox Bank",
    )
    db.add(item)
    db.flush()
    bank = Bank(owner_id=owner_id, plaid_item_id=item.id)
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return bank


def test_accounts_list_filters_by_bank_id(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    token, user_id = register_and_login("bank-filter@example.com")
    bank = _make_bank(db, user_id)

    linked_account = Account(
        user_id=user_id,
        name="Plaid Checking",
        account_type="checking",
        balance=Decimal("0"),
        is_plaid_linked=True,
        bank_id=bank.id,
        plaid_account_id="plaid-acc-1",
    )
    db.add(linked_account)
    db.commit()

    client.post(
        "/api/v1/accounts",
        json={"name": "Manual savings", "account_type": "savings", "balance": "0"},
        headers=_auth_headers(token),
    )

    unfiltered = client.get("/api/v1/accounts", headers=_auth_headers(token)).json()["data"]
    assert len(unfiltered) == 2

    filtered = client.get(
        "/api/v1/accounts", params={"bank_id": str(bank.id)}, headers=_auth_headers(token)
    ).json()["data"]
    assert len(filtered) == 1
    assert filtered[0]["name"] == "Plaid Checking"
    assert filtered[0]["bank_id"] == str(bank.id)
