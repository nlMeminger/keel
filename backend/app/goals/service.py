import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.errors import AppError
from app.goals.models import GoalContribution, SavingsGoal


def compute_goal_progress(db: DbSession, goal_id: uuid.UUID) -> Decimal:
    stmt = select(func.coalesce(func.sum(GoalContribution.amount), 0)).where(
        GoalContribution.goal_id == goal_id
    )
    return db.scalar(stmt) or Decimal("0")


def create_goal(
    db: DbSession, user: User, name: str, target_amount: Decimal, target_date: date | None
) -> SavingsGoal:
    goal = SavingsGoal(
        user_id=user.id, name=name, target_amount=target_amount, target_date=target_date
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def get_goal(db: DbSession, user: User, goal_id: uuid.UUID) -> SavingsGoal:
    goal = db.scalar(
        select(SavingsGoal).where(SavingsGoal.id == goal_id, SavingsGoal.user_id == user.id)
    )
    if goal is None:
        raise AppError(404, "not_found", "Savings goal not found.")
    return goal


def list_goals_stmt(user: User) -> Select[SavingsGoal]:
    return (
        select(SavingsGoal).where(SavingsGoal.user_id == user.id).order_by(SavingsGoal.created_at)
    )


def update_goal(
    db: DbSession,
    user: User,
    goal_id: uuid.UUID,
    name: str | None,
    target_amount: Decimal | None,
    target_date: date | None,
) -> SavingsGoal:
    goal = get_goal(db, user, goal_id)
    if name is not None:
        goal.name = name
    if target_amount is not None:
        goal.target_amount = target_amount
    if target_date is not None:
        goal.target_date = target_date
    db.commit()
    db.refresh(goal)
    return goal


def delete_goal(db: DbSession, user: User, goal_id: uuid.UUID) -> None:
    goal = get_goal(db, user, goal_id)
    db.delete(goal)
    db.commit()


def add_contribution(
    db: DbSession,
    user: User,
    goal_id: uuid.UUID,
    amount: Decimal,
    contribution_date: date,
    note: str | None,
) -> SavingsGoal:
    """Ownership is checked once via the parent goal lookup; returns the updated goal (not
    the raw contribution) so the caller can report fresh progress without a second fetch."""
    goal = get_goal(db, user, goal_id)
    contribution = GoalContribution(
        goal_id=goal.id, amount=amount, date=contribution_date, note=note
    )
    db.add(contribution)
    db.commit()
    db.refresh(goal)
    return goal
