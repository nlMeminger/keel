import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params
from app.metrics import service
from app.metrics.schemas import (
    MetricBulkCreateRequest,
    MetricCreateRequest,
    MetricPublic,
    MetricUpdateRequest,
)

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("")
def list_metrics(
    metric_type: str | None = Query(default=None, alias="type"),
    account_id: uuid.UUID | None = Query(default=None),
    asset_id: uuid.UUID | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = service.list_metrics_stmt(
        user,
        metric_type=metric_type,
        account_id=account_id,
        asset_id=asset_id,
        date_from=date_from,
        date_to=date_to,
    )
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [MetricPublic.model_validate(row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.post("", response_model=Envelope[MetricPublic], status_code=status.HTTP_201_CREATED)
def create_metric(
    body: MetricCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, MetricPublic]:
    metric = service.create_metric(
        db,
        user,
        metric_type=body.type,
        value=body.value,
        metric_date=body.date,
        note=body.note,
        account_id=body.account_id,
        asset_id=body.asset_id,
    )
    return {"data": MetricPublic.model_validate(metric)}


@router.post(
    "/bulk", response_model=Envelope[list[MetricPublic]], status_code=status.HTTP_201_CREATED
)
def bulk_create_metrics(
    body: MetricBulkCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, list[MetricPublic]]:
    entries = [
        (entry.type, entry.value, entry.date, entry.note, entry.account_id, entry.asset_id)
        for entry in body.entries
    ]
    metrics = service.bulk_create_metrics(db, user, entries)
    return {"data": [MetricPublic.model_validate(m) for m in metrics]}


@router.patch("/{metric_id}", response_model=Envelope[MetricPublic])
def update_metric(
    metric_id: uuid.UUID,
    body: MetricUpdateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, MetricPublic]:
    metric = service.update_metric(
        db,
        user,
        metric_id,
        metric_type=body.type,
        value=body.value,
        metric_date=body.date,
        note=body.note,
    )
    return {"data": MetricPublic.model_validate(metric)}


@router.delete("/{metric_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_metric(
    metric_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    service.delete_metric(db, user, metric_id)
