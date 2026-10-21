import logging
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session as OrmSession

from app.auth.models import User
from app.banks.models import Bank, PlaidItem
from app.webhooks.service import handle_webhook


def _make_user(db: OrmSession) -> User:
    user = User(email="webhook-user@example.com", password_hash="hashed", name="Tester")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_bank(db: OrmSession, owner_id: uuid.UUID, removed_at: datetime | None = None) -> Bank:
    item = PlaidItem(
        access_token="irrelevant",
        item_id=f"item-{uuid.uuid4()}",
        institution_id="ins_1",
        institution_name="Sandbox Bank",
        removed_at=removed_at,
    )
    db.add(item)
    db.flush()
    bank = Bank(owner_id=owner_id, plaid_item_id=item.id)
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return bank


def _item_id(db: OrmSession, bank: Bank) -> str:
    item = db.get(PlaidItem, bank.plaid_item_id)
    assert item is not None
    return item.item_id


def test_item_login_required_error_sets_needs_reauth(db: OrmSession) -> None:
    user = _make_user(db)
    bank = _make_bank(db, user.id)

    result = handle_webhook(
        db,
        {
            "webhook_type": "ITEM",
            "webhook_code": "ERROR",
            "item_id": _item_id(db, bank),
            "error": {"error_code": "ITEM_LOGIN_REQUIRED"},
        },
    )

    assert result["health"] == "needs_reauth"
    db.refresh(bank)
    assert bank.health == "needs_reauth"


def test_other_item_error_sets_health_error(db: OrmSession) -> None:
    user = _make_user(db)
    bank = _make_bank(db, user.id)

    result = handle_webhook(
        db,
        {
            "webhook_type": "ITEM",
            "webhook_code": "ERROR",
            "item_id": _item_id(db, bank),
            "error": {"error_code": "INTERNAL_SERVER_ERROR"},
        },
    )

    assert result["health"] == "error"


def test_pending_expiration_sets_needs_reauth(db: OrmSession) -> None:
    user = _make_user(db)
    bank = _make_bank(db, user.id)

    result = handle_webhook(
        db,
        {
            "webhook_type": "ITEM",
            "webhook_code": "PENDING_EXPIRATION",
            "item_id": _item_id(db, bank),
        },
    )

    assert result["health"] == "needs_reauth"


def test_login_repaired_restores_healthy(db: OrmSession) -> None:
    user = _make_user(db)
    bank = _make_bank(db, user.id)
    bank.health = "needs_reauth"
    db.commit()

    result = handle_webhook(
        db,
        {"webhook_type": "ITEM", "webhook_code": "LOGIN_REPAIRED", "item_id": _item_id(db, bank)},
    )

    assert result["health"] == "healthy"


def test_unknown_item_id_is_ignored_without_error(db: OrmSession) -> None:
    result = handle_webhook(
        db,
        {
            "webhook_type": "ITEM",
            "webhook_code": "LOGIN_REPAIRED",
            "item_id": "item-does-not-exist",
        },
    )
    assert result["status"] == "ignored"


def test_webhook_for_removed_item_triggers_ghost_item_alert(
    db: OrmSession, caplog: pytest.LogCaptureFixture
) -> None:
    user = _make_user(db)
    bank = _make_bank(db, user.id, removed_at=datetime.now(UTC))

    with caplog.at_level(logging.ERROR, logger="app.webhooks"):
        result = handle_webhook(
            db,
            {
                "webhook_type": "TRANSACTIONS",
                "webhook_code": "SYNC_UPDATES_AVAILABLE",
                "item_id": _item_id(db, bank),
            },
        )

    assert result["status"] == "ghost_item_alert"
    assert any("removed Plaid item" in record.message for record in caplog.records)
