from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from app.admin.audit import record_audit_log
from app.admin.dependencies import require_admin
from app.admin.schemas import CategoriesSeedResponseData, InstitutionsSeedResponseData
from app.auth.models import User
from app.banks.seed import seed_institutions
from app.categories.seed import seed_categories
from app.core.envelope import Envelope
from app.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/categories/seed", response_model=Envelope[CategoriesSeedResponseData])
def seed_categories_route(
    db: DbSession = Depends(get_db), admin: User = Depends(require_admin)
) -> dict[str, CategoriesSeedResponseData]:
    created = seed_categories(db)
    record_audit_log(db, admin, "categories.seed", "system", None, {"created": created})
    return {"data": CategoriesSeedResponseData(created=created)}


@router.post("/banks/seed", response_model=Envelope[InstitutionsSeedResponseData])
def seed_institutions_route(
    db: DbSession = Depends(get_db), admin: User = Depends(require_admin)
) -> dict[str, InstitutionsSeedResponseData]:
    result = seed_institutions(db)
    record_audit_log(db, admin, "institutions.seed", "system", None, result)
    return {"data": InstitutionsSeedResponseData(**result)}
