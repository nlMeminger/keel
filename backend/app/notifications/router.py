import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params
from app.notifications import service
from app.notifications.schemas import NotificationPublic, NotificationUpdateRequest

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = Query(default=False),
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = service.list_notifications_stmt(user, unread_only)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [NotificationPublic.from_notification(row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.patch("/{notification_id}", response_model=Envelope[NotificationPublic])
def update_notification(
    notification_id: uuid.UUID,
    body: NotificationUpdateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, NotificationPublic]:
    row = service.set_read(db, user, notification_id, body.read)
    return {"data": NotificationPublic.from_notification(row)}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_notification(
    notification_id: uuid.UUID,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    service.dismiss_notification(db, user, notification_id)
