from plaid.model.country_code import CountryCode
from plaid.model.institutions_get_request import InstitutionsGetRequest
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.banks.models import Institution
from app.core.plaid_client import get_plaid_client

# Plaid's per-page max; a single page of the top institutions is enough for v1 — not the
# full tens-of-thousands-institution catalog, which nothing in the app browses yet.
_PAGE_SIZE = 500


def seed_institutions(db: DbSession) -> dict[str, int]:
    """POST /admin/banks/seed (API_SPEC.md §18) — (re)seeds the institution reference list
    from Plaid's real `/institutions/get`, idempotent on `plaid_institution_id`.

    Calls Plaid directly rather than through banks/service.py's call_plaid: that requires a
    user_id to attribute the PlaidAPICall row to, but this is a system-level reference-data
    refresh with no one user to bill it to — same precedent as
    banks/service.py::reconcile_removed_plaid_items.
    """
    client = get_plaid_client()
    response = client.institutions_get(
        InstitutionsGetRequest(count=_PAGE_SIZE, offset=0, country_codes=[CountryCode("US")])
    )

    created = updated = 0
    for inst in response.institutions:
        existing = db.scalar(
            select(Institution).where(Institution.plaid_institution_id == inst.institution_id)
        )
        if existing is not None:
            existing.name = inst.name
            existing.logo_url = inst.logo
            updated += 1
        else:
            db.add(
                Institution(
                    plaid_institution_id=inst.institution_id, name=inst.name, logo_url=inst.logo
                )
            )
            created += 1
    db.commit()
    return {"created": created, "updated": updated}
