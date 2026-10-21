from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.accounts.router import router as accounts_router
from app.admin.users_router import router as admin_users_router
from app.assets.router import router as assets_router
from app.auth.router import router as auth_router
from app.banks.router import router as banks_router
from app.budgets.router import router as budgets_router
from app.categories.router import router as categories_router
from app.category_rules.router import router as category_rules_router
from app.config import settings
from app.core.errors import register_error_handlers
from app.dashboard.router import router as dashboard_router
from app.goals.router import router as goals_router
from app.holdings.router import router as holdings_router
from app.merchants.router import router as merchants_router
from app.metrics.router import router as metrics_router
from app.notifications.router import router as notifications_router
from app.plaid_link.router import router as plaid_link_router
from app.recurring_transactions.router import router as recurring_transactions_router
from app.reports.router import router as reports_router
from app.sync.router import router as sync_router
from app.transactions.router import router as transactions_router
from app.webhooks.router import router as webhooks_router

app = FastAPI(title="Money App API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)

app.include_router(accounts_router, prefix="/api/v1")
app.include_router(admin_users_router, prefix="/api/v1")
app.include_router(assets_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(banks_router, prefix="/api/v1")
app.include_router(budgets_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
app.include_router(category_rules_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(goals_router, prefix="/api/v1")
app.include_router(holdings_router, prefix="/api/v1")
app.include_router(merchants_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(plaid_link_router, prefix="/api/v1")
app.include_router(recurring_transactions_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")
app.include_router(webhooks_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
