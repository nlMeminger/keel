import uuid

from sqlalchemy import Select, select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.errors import AppError
from app.merchants.models import Merchant


def create_merchant(db: DbSession, user: User, name: str, aliases: list[str]) -> Merchant:
    merchant = Merchant(user_id=user.id, name=name, aliases=aliases)
    db.add(merchant)
    db.commit()
    db.refresh(merchant)
    return merchant


def get_merchant(db: DbSession, user: User, merchant_id: uuid.UUID) -> Merchant:
    merchant = db.scalar(
        select(Merchant).where(Merchant.id == merchant_id, Merchant.user_id == user.id)
    )
    if merchant is None:
        raise AppError(404, "not_found", "Merchant not found.")
    return merchant


def list_merchants_stmt(user: User) -> Select[Merchant]:
    return select(Merchant).where(Merchant.user_id == user.id).order_by(Merchant.name)


def update_merchant(
    db: DbSession,
    user: User,
    merchant_id: uuid.UUID,
    name: str | None,
    aliases: list[str] | None,
) -> Merchant:
    merchant = get_merchant(db, user, merchant_id)
    if name is not None:
        merchant.name = name
    if aliases is not None:
        merchant.aliases = aliases
    db.commit()
    db.refresh(merchant)
    return merchant


def delete_merchant(db: DbSession, user: User, merchant_id: uuid.UUID) -> None:
    merchant = get_merchant(db, user, merchant_id)
    db.delete(merchant)
    db.commit()
