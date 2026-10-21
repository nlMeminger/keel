from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.budgets.schemas import BudgetPublic
from app.dashboard import service
from app.dashboard.schemas import CreditScoreSummary, DashboardSummary
from app.database import get_db
from app.dependencies import get_current_user
from app.reports import service as reports_service
from app.transactions.schemas import TransactionPublic

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_summary(
    db: DbSession = Depends(get_db), user: User = Depends(get_current_user)
) -> dict[str, DashboardSummary]:
    net_worth = reports_service.current_net_worth(db, user)
    delta = service.net_worth_delta(db, user, net_worth)
    inflow, outflow = service.this_month_cash_flow(db, user)

    credit_score = service.latest_credit_score(db, user)
    credit_summary = (
        CreditScoreSummary(
            value=credit_score[0].value, date=credit_score[0].date, trend=credit_score[1]
        )
        if credit_score is not None
        else None
    )

    budgets = [
        BudgetPublic.from_budget(budget, spend) for budget, spend in service.budget_status(db, user)
    ]
    recent = [
        TransactionPublic.model_validate(txn) for txn in service.recent_transactions(db, user)
    ]

    return {
        "data": DashboardSummary(
            net_worth=net_worth,
            net_worth_delta=delta,
            this_month_inflow=inflow,
            this_month_outflow=outflow,
            recent_transactions=recent,
            budgets=budgets,
            latest_credit_score=credit_summary,
        )
    }
