import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.errors import AppError
from app.goals.models import GoalContribution, SavingsGoal
from app.notifications import service as notifications_service

#: Percent-of-target milestones that create a Notification the first time they're crossed
#: (API_SPEC.md §10). Goals have no period to reset within, unlike budgets — each milestone
#: notifies at most once ever per goal.
MILESTONE_PERCENTAGES = (50, 100)


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


def _notify_if_milestone_crossed(db: DbSession, user: User, goal: SavingsGoal) -> None:
    """Checked inline on every contribution (API_SPEC.md §10), not a scheduled job. No period
    to scope dedup to — a milestone notifies at most once ever per goal."""
    if goal.target_amount <= 0:
        return
    progress = compute_goal_progress(db, goal.id)
    percent = (progress / goal.target_amount) * 100

    for threshold in MILESTONE_PERCENTAGES:
        if percent < threshold:
            continue
        notification_type = f"goal_milestone_{threshold}"
        if notifications_service.notification_already_sent(
            db, user.id, notification_type, "savings_goal", goal.id
        ):
            continue
        notifications_service.create_notification(
            db,
            user.id,
            notification_type,
            title=f'"{goal.name}" reached {threshold}% of its target',
            body=f"Progress is now {progress} of {goal.target_amount}.",
            related_type="savings_goal",
            related_id=goal.id,
        )


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
    _notify_if_milestone_crossed(db, user, goal)
    db.refresh(goal)
    return goal
