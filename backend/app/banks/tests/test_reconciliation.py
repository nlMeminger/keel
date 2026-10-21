"""Scheduled ghost-item sweep (ROADMAP 7.11) — the other half of the ghost-item check
alongside the webhook-side one in app.webhooks.tests.test_processing. Exercised against
Plaid's real sandbox API, same as test_sandbox_integration.py: skipped entirely when
PLAID_CLIENT_ID/PLAID_SECRET aren't configured."""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as OrmSession

from app.banks.models import Bank, PlaidItem
from app.banks.service import reconcile_removed_plaid_items
from app.banks.tests.test_sandbox_integration import _link_sandbox_bank, requires_sandbox


@requires_sandbox
def test_reconcile_finds_no_ghost_in_a_genuinely_removed_item(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
) -> None:
    token, _user_id = register_and_login("reconcile-clean@example.com")
    bank = _link_sandbox_bank(client, token)
    item_id = db.get(Bank, uuid.UUID(str(bank["id"])))
    assert item_id is not None
    plaid_item_id = item_id.plaid_item_id

    delete_resp = client.delete(
        f"/api/v1/banks/{bank['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert delete_resp.status_code == 204

    result = reconcile_removed_plaid_items(db)

    assert result["checked"] >= 1
    assert result["ghost_items"] == 0
    item = db.get(PlaidItem, plaid_item_id)
    assert item is not None and item.removed_at is not None


@requires_sandbox
def test_reconcile_flags_a_removed_item_plaid_still_considers_live(
    client: TestClient,
    register_and_login: Callable[[str], tuple[str, uuid.UUID]],
    db: OrmSession,
    caplog: pytest.LogCaptureFixture,
) -> None:
    token, _user_id = register_and_login("reconcile-ghost@example.com")
    bank = _link_sandbox_bank(client, token)
    bank_row = db.get(Bank, uuid.UUID(str(bank["id"])))
    assert bank_row is not None

    # Marks removed_at by hand, skipping the real item/remove call unlink_bank would make —
    # simulates the desync case this sweep exists to catch, per ROADMAP 7.11's success
    # criteria: our records say removed, but Plaid was never actually told.
    item = db.get(PlaidItem, bank_row.plaid_item_id)
    assert item is not None
    item.removed_at = datetime.now(UTC)
    db.commit()

    with caplog.at_level(logging.ERROR, logger="app.banks"):
        result = reconcile_removed_plaid_items(db)

    assert result["ghost_items"] == 1
    assert any("still reports removed item" in record.message for record in caplog.records)
