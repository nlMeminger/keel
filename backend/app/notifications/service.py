import uuid
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.errors import AppError
from app.notifications.models import Notification


def create_notification(
    db: DbSession,
    user_id: uuid.UUID,
    notification_type: str,
    title: str,
    body: str,
    related_type: str | None = None,
    related_id: uuid.UUID | None = None,
) -> Notification:
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        body=body,
        related_type=related_type,
        related_id=related_id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


def notification_already_sent(
    db: DbSession,
    user_id: uuid.UUID,
    notification_type: str,
    related_type: str,
    related_id: uuid.UUID,
    since: datetime | None = None,
) -> bool:
    """Used by threshold-crossing write paths (budgets/goals, API_SPEC.md §9/§10) to avoid a
    duplicate notification for the same threshold. `since` scopes the check to the current
    period for budgets (monthly) so next month's crossing still fires; goals have no period,
    so their callers omit it and the threshold notifies at most once ever per goal."""
    stmt = select(Notification.id).where(
        Notification.user_id == user_id,
        Notification.type == notification_type,
        Notification.related_type == related_type,
        Notification.related_id == related_id,
    )
    if since is not None:
        stmt = stmt.where(Notification.created_at >= since)
    return db.scalar(stmt) is not None


def get_notification(db: DbSession, user: User, notification_id: uuid.UUID) -> Notification:
    row = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id
        )
    )
    if row is None:
        raise AppError(404, "not_found", "Notification not found.")
    return row


def list_notifications_stmt(user: User, unread_only: bool) -> Select[Notification]:
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    return stmt.order_by(Notification.created_at.desc())


def set_read(db: DbSession, user: User, notification_id: uuid.UUID, read: bool) -> Notification:
    row = get_notification(db, user, notification_id)
    row.read_at = datetime.now(UTC) if read else None
    db.commit()
    db.refresh(row)
    return row


def dismiss_notification(db: DbSession, user: User, notification_id: uuid.UUID) -> None:
    row = get_notification(db, user, notification_id)
    db.delete(row)
    db.commit()
