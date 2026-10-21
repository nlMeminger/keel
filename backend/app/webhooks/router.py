import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session as DbSession

from app.database import get_db
from app.webhooks import service
from app.webhooks.verification import verify_webhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/plaid")
async def plaid_webhook(
    request: Request, db: DbSession = Depends(get_db)
) -> dict[str, dict[str, str]]:
    """Inbound Plaid webhook (API_SPEC.md §17) — not user-authenticated, verified by the
    Plaid-Verification JWT signature instead (API_SPEC.md Conventions)."""
    raw_body = await request.body()
    verify_webhook(request.headers.get("Plaid-Verification"), raw_body)
    payload: dict[str, Any] = json.loads(raw_body)
    result = service.handle_webhook(db, payload)
    return {"data": result}
