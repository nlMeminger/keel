import uuid
from datetime import datetime

from pydantic import BaseModel

from app.notifications.models import Notification


class NotificationUpdateRequest(BaseModel):
    read: bool


class NotificationPublic(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    related_type: str | None
    related_id: uuid.UUID | None
    read_at: datetime | None
    created_at: datetime

    @classmethod
    def from_notification(cls, row: Notification) -> "NotificationPublic":
        return cls(
            id=row.id,
            type=row.type,
            title=row.title,
            body=row.body,
            related_type=row.related_type,
            related_id=row.related_id,
            read_at=row.read_at,
            created_at=row.created_at,
        )
