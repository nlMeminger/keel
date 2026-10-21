import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session as OrmSession

from app.auth.models import User
from app.banks.models import Bank, PlaidItem


def _make_user(db: OrmSession) -> User:
    user = User(email="owner@example.com", password_hash="hashed", name="Owner")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_plaid_item(db: OrmSession, item_id: str = "item-sandbox-1") -> PlaidItem:
    item = PlaidItem(
        access_token="encrypted-access-token",
        item_id=item_id,
        institution_id="ins_1",
        institution_name="Sandbox Bank",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_bank_can_exist_with_linked_plaid_item_and_zero_accounts(db: OrmSession) -> None:
    user = _make_user(db)
    item = _make_plaid_item(db)

    bank = Bank(owner_id=user.id, plaid_item_id=item.id)
    db.add(bank)
    db.commit()
    db.refresh(bank)

    assert bank.health == "healthy"
    assert bank.last_synced_at is None


def test_plaid_item_defaults(db: OrmSession) -> None:
    item = _make_plaid_item(db)
    assert item.cursor is None
    assert item.removed_at is None


def test_plaid_item_id_is_unique(db: OrmSession) -> None:
    _make_plaid_item(db, item_id="dup-item")
    dup = PlaidItem(
        access_token="another-token",
        item_id="dup-item",
        institution_id="ins_2",
        institution_name="Other Bank",
    )
    db.add(dup)
    try:
        db.commit()
        raised = False
    except Exception:
        db.rollback()
        raised = True
    assert raised


def test_invalid_bank_health_rejected_at_db_level(db: OrmSession) -> None:
    user = _make_user(db)
    item = _make_plaid_item(db)
    bank = Bank(owner_id=user.id, plaid_item_id=item.id, health="bogus")
    db.add(bank)
    try:
        db.commit()
        raised = False
    except Exception:
        db.rollback()
        raised = True
    assert raised


def test_bank_plaid_item_id_is_unique_one_to_one(db: OrmSession) -> None:
    user = _make_user(db)
    item = _make_plaid_item(db)
    db.add(Bank(owner_id=user.id, plaid_item_id=item.id))
    db.commit()

    dup_bank = Bank(owner_id=user.id, plaid_item_id=item.id)
    db.add(dup_bank)
    try:
        db.commit()
        raised = False
    except Exception:
        db.rollback()
        raised = True
    assert raised


def test_bank_cascades_on_plaid_item_delete(db: OrmSession) -> None:
    user = _make_user(db)
    item = _make_plaid_item(db)
    bank = Bank(owner_id=user.id, plaid_item_id=item.id)
    db.add(bank)
    db.commit()
    bank_id = bank.id

    db.delete(item)
    db.commit()

    assert db.get(Bank, bank_id) is None


def test_bank_cascades_on_user_delete(db: OrmSession) -> None:
    user = _make_user(db)
    item = _make_plaid_item(db)
    bank = Bank(owner_id=user.id, plaid_item_id=item.id)
    db.add(bank)
    db.commit()
    bank_id = bank.id

    db.delete(user)
    db.commit()

    assert db.get(Bank, bank_id) is None


def test_banks_table_has_owner_id_index(db: OrmSession) -> None:
    rows = db.execute(text("SELECT indexdef FROM pg_indexes WHERE tablename = 'banks'")).scalars()
    assert any("owner_id" in indexdef for indexdef in rows)


def test_bank_id_is_uuid(db: OrmSession) -> None:
    user = _make_user(db)
    item = _make_plaid_item(db)
    bank = Bank(owner_id=user.id, plaid_item_id=item.id)
    db.add(bank)
    db.commit()
    db.refresh(bank)
    assert isinstance(bank.id, uuid.UUID)
