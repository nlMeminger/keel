import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params
from app.goals import service
from app.goals.schemas import (
    GoalContributionCreateRequest,
    SavingsGoalCreateRequest,
    SavingsGoalPublic,
    SavingsGoalUpdateRequest,
)

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("")
def list_goals(
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = service.list_goals_stmt(user)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    data = [
        SavingsGoalPublic.from_goal(row, service.compute_goal_progress(db, row.id)) for row in rows
    ]
    return {"data": data, "pagination": meta.model_dump()}


@router.post("", response_model=Envelope[SavingsGoalPublic], status_code=status.HTTP_201_CREATED)
def create_goal(
    body: SavingsGoalCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, SavingsGoalPublic]:
    goal = service.create_goal(
        db, user, name=body.name, target_amount=body.target_amount, target_date=body.target_date
    )
    return {"data": SavingsGoalPublic.from_goal(goal, Decimal("0"))}


@router.patch("/{goal_id}", response_model=Envelope[SavingsGoalPublic])
def update_goal(
    goal_id: uuid.UUID,
    body: SavingsGoalUpdateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, SavingsGoalPublic]:
    goal = service.update_goal(
        db,
        user,
        goal_id,
        name=body.name,
        target_amount=body.target_amount,
        target_date=body.target_date,
    )
    progress = service.compute_goal_progress(db, goal.id)
    return {"data": SavingsGoalPublic.from_goal(goal, progress)}


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    service.delete_goal(db, user, goal_id)


@router.post(
    "/{goal_id}/contributions",
    response_model=Envelope[SavingsGoalPublic],
    status_code=status.HTTP_201_CREATED,
)
def add_contribution(
    goal_id: uuid.UUID,
    body: GoalContributionCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, SavingsGoalPublic]:
    goal = service.add_contribution(
        db, user, goal_id, amount=body.amount, contribution_date=body.date, note=body.note
    )
    progress = service.compute_goal_progress(db, goal.id)
    return {"data": SavingsGoalPublic.from_goal(goal, progress)}
