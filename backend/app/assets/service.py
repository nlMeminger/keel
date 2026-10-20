import uuid
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session as DbSession

from app.assets.models import Asset
from app.auth.models import User
from app.core.errors import AppError


def create_asset(
    db: DbSession, user: User, name: str, asset_type: str, current_value: Decimal
) -> Asset:
    asset = Asset(user_id=user.id, name=name, asset_type=asset_type, current_value=current_value)
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def get_asset(db: DbSession, user: User, asset_id: uuid.UUID) -> Asset:
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, Asset.user_id == user.id))
    if asset is None:
        raise AppError(404, "not_found", "Asset not found.")
    return asset


def list_assets_stmt(user: User) -> Select[Asset]:
    return select(Asset).where(Asset.user_id == user.id).order_by(Asset.created_at)


def update_asset(
    db: DbSession,
    user: User,
    asset_id: uuid.UUID,
    name: str | None,
    asset_type: str | None,
    current_value: Decimal | None,
) -> Asset:
    asset = get_asset(db, user, asset_id)
    if name is not None:
        asset.name = name
    if asset_type is not None:
        asset.asset_type = asset_type
    if current_value is not None:
        asset.current_value = current_value
    db.commit()
    db.refresh(asset)
    return asset


def delete_asset(db: DbSession, user: User, asset_id: uuid.UUID) -> None:
    asset = get_asset(db, user, asset_id)
    db.delete(asset)
    db.commit()
