import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.category_rules import service
from app.category_rules.schemas import (
    CategoryRuleApplyResponse,
    CategoryRuleConditions,
    CategoryRuleCreateRequest,
    CategoryRulePublic,
    CategoryRuleTestResponse,
    CategoryRuleUpdateRequest,
    TransactionMatchPublic,
)
from app.category_rules.tasks import apply_category_rules_task
from app.core.envelope import Envelope, paginate
from app.database import get_db
from app.dependencies import PaginationParams, get_current_user, pagination_params
from app.jobs.service import create_job

router = APIRouter(prefix="/category-rules", tags=["category-rules"])


@router.get("")
def list_rules(
    pagination: PaginationParams = Depends(pagination_params),
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    stmt = service.list_rules_stmt(user)
    rows, meta = paginate(db, stmt, pagination.page, pagination.page_size)
    return {
        "data": [CategoryRulePublic.from_rule(row) for row in rows],
        "pagination": meta.model_dump(),
    }


@router.post("", response_model=Envelope[CategoryRulePublic], status_code=status.HTTP_201_CREATED)
def create_rule(
    body: CategoryRuleCreateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, CategoryRulePublic]:
    rule = service.create_rule(
        db,
        user,
        category_id=body.category_id,
        merchant_contains=body.merchant_contains,
        amount_min=body.amount_min,
        amount_max=body.amount_max,
        account_id=body.account_id,
        priority=body.priority,
        active=body.active,
    )
    return {"data": CategoryRulePublic.from_rule(rule)}


@router.post("/test", response_model=Envelope[CategoryRuleTestResponse])
def test_rule(
    body: CategoryRuleConditions,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, CategoryRuleTestResponse]:
    matches = service.find_matches_for_conditions(
        db,
        user,
        merchant_contains=body.merchant_contains,
        amount_min=body.amount_min,
        amount_max=body.amount_max,
        account_id=body.account_id,
    )
    return {
        "data": CategoryRuleTestResponse(
            matches=[TransactionMatchPublic.model_validate(txn) for txn in matches]
        )
    }


@router.post(
    "/apply",
    response_model=Envelope[CategoryRuleApplyResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
def apply_rules(
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, CategoryRuleApplyResponse]:
    job = create_job(db, "category_rule_apply", owner_id=user.id)
    apply_category_rules_task.delay(str(job.id), str(user.id))
    return {"data": CategoryRuleApplyResponse(job_id=job.id)}


@router.patch("/{rule_id}", response_model=Envelope[CategoryRulePublic])
def update_rule(
    rule_id: uuid.UUID,
    body: CategoryRuleUpdateRequest,
    db: DbSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, CategoryRulePublic]:
    fields = body.model_dump(exclude_unset=True)
    rule = service.update_rule(db, user, rule_id, fields)
    return {"data": CategoryRulePublic.from_rule(rule)}


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: uuid.UUID, db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> None:
    service.delete_rule(db, user, rule_id)
