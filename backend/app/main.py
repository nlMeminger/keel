from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.accounts.router import router as accounts_router
from app.assets.router import router as assets_router
from app.auth.router import router as auth_router
from app.budgets.router import router as budgets_router
from app.categories.router import router as categories_router
from app.config import settings
from app.core.errors import register_error_handlers
from app.goals.router import router as goals_router
from app.holdings.router import router as holdings_router
from app.merchants.router import router as merchants_router
from app.metrics.router import router as metrics_router
from app.sync.router import router as sync_router
from app.transactions.router import router as transactions_router

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
app.include_router(assets_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(budgets_router, prefix="/api/v1")
app.include_router(categories_router, prefix="/api/v1")
app.include_router(goals_router, prefix="/api/v1")
app.include_router(holdings_router, prefix="/api/v1")
app.include_router(merchants_router, prefix="/api/v1")
app.include_router(metrics_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")
app.include_router(transactions_router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
