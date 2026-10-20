import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.budgets import service
from app.budgets.schemas import BudgetCreateRequest, BudgetPublic, BudgetUpdateRequest
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("")
def list_budgets(
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = service.list_budgets_stmt(user)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    data = [
        BudgetPublic.from_budget(row, service.compute_budget_spend(db, user, row)) for row in rows
    ]
    return {"data": data, "pagination": meta.model_dump()}


@router.post("", response_model=Envelope[BudgetPublic], status_code=status.HTTP_201_CREATED)
def create_budget(
    body: BudgetCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, BudgetPublic]:
    budget = service.create_budget(
        db,
        user,
        category_id=body.category_id,
        amount_limit=body.amount_limit,
        start_date=body.start_date,
    )
    spend_so_far = service.compute_budget_spend(db, user, budget)
    return {"data": BudgetPublic.from_budget(budget, spend_so_far)}


@router.patch("/{budget_id}", response_model=Envelope[BudgetPublic])
def update_budget(
    budget_id: uuid.UUID,
    body: BudgetUpdateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, BudgetPublic]:
    fields = body.model_dump(exclude_unset=True)
    budget = service.update_budget(db, user, budget_id, fields)
    spend_so_far = service.compute_budget_spend(db, user, budget)
    return {"data": BudgetPublic.from_budget(budget, spend_so_far)}


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    service.delete_budget(db, user, budget_id)
