import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, select
from sqlalchemy.orm import Session as DbSession

from app.accounts.models import Account
from app.assets.models import Asset
from app.auth.models import User
from app.core.errors import AppError
from app.metrics.models import Metric


def _validate_account_owned(db: DbSession, user: User, account_id: uuid.UUID | None) -> None:
    if account_id is None:
        return
    account = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user.id))
    if account is None:
        raise AppError(404, "not_found", "Account not found.")


def _validate_asset_owned(db: DbSession, user: User, asset_id: uuid.UUID | None) -> None:
    if asset_id is None:
        return
    asset = db.scalar(select(Asset).where(Asset.id == asset_id, Asset.user_id == user.id))
    if asset is None:
        raise AppError(404, "not_found", "Asset not found.")


def create_metric(
    db: DbSession,
    user: User,
    metric_type: str,
    value: Decimal,
    metric_date: date,
    note: str | None,
    account_id: uuid.UUID | None,
    asset_id: uuid.UUID | None,
) -> Metric:
    """Always an insert, never a find-and-update — this is what makes the append-only
    value-history behavior (4.9's auto-write included) correct. Reused directly by the
    Account/Asset PATCH auto-write hook, not just the manual POST route."""
    _validate_account_owned(db, user, account_id)
    _validate_asset_owned(db, user, asset_id)
    metric = Metric(
        user_id=user.id,
        type=metric_type,
        value=value,
        date=metric_date,
        note=note,
        account_id=account_id,
        asset_id=asset_id,
    )
    db.add(metric)
    db.commit()
    db.refresh(metric)
    return metric


def bulk_create_metrics(
    db: DbSession,
    user: User,
    entries: list[tuple[str, Decimal, date, str | None, uuid.UUID | None, uuid.UUID | None]],
) -> list[Metric]:
    """All-or-nothing: if any entry fails ownership validation, nothing in the batch commits."""
    metrics = []
    for metric_type, value, metric_date, note, account_id, asset_id in entries:
        _validate_account_owned(db, user, account_id)
        _validate_asset_owned(db, user, asset_id)
        metric = Metric(
            user_id=user.id,
            type=metric_type,
            value=value,
            date=metric_date,
            note=note,
            account_id=account_id,
            asset_id=asset_id,
        )
        db.add(metric)
        metrics.append(metric)
    db.commit()
    for metric in metrics:
        db.refresh(metric)
    return metrics


def get_metric(db: DbSession, user: User, metric_id: uuid.UUID) -> Metric:
    metric = db.scalar(select(Metric).where(Metric.id == metric_id, Metric.user_id == user.id))
    if metric is None:
        raise AppError(404, "not_found", "Metric not found.")
    return metric


def list_metrics_stmt(
    user: User,
    metric_type: str | None,
    account_id: uuid.UUID | None,
    asset_id: uuid.UUID | None,
    date_from: date | None,
    date_to: date | None,
) -> Select[Metric]:
    stmt = select(Metric).where(Metric.user_id == user.id)
    if metric_type is not None:
        stmt = stmt.where(Metric.type == metric_type)
    if account_id is not None:
        stmt = stmt.where(Metric.account_id == account_id)
    if asset_id is not None:
        stmt = stmt.where(Metric.asset_id == asset_id)
    if date_from is not None:
        stmt = stmt.where(Metric.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Metric.date <= date_to)
    return stmt.order_by(Metric.date.desc())


def update_metric(
    db: DbSession,
    user: User,
    metric_id: uuid.UUID,
    metric_type: str | None,
    value: Decimal | None,
    metric_date: date | None,
    note: str | None,
) -> Metric:
    metric = get_metric(db, user, metric_id)
    if metric_type is not None:
        metric.type = metric_type
    if value is not None:
        metric.value = value
    if metric_date is not None:
        metric.date = metric_date
    if note is not None:
        metric.note = note
    db.commit()
    db.refresh(metric)
    return metric


def delete_metric(db: DbSession, user: User, metric_id: uuid.UUID) -> None:
    metric = get_metric(db, user, metric_id)
    db.delete(metric)
    db.commit()
