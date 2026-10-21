"""Route-level checks that don't require a real Plaid call — the ownership check on
bank_id happens before the service layer ever touches the Plaid client."""

import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


def test_link_token_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/plaid/link-token")
    assert response.status_code == 401


def test_exchange_token_requires_auth(client: TestClient) -> None:
    response = client.post("/api/v1/plaid/exchange-token", json={"public_token": "public-x"})
    assert response.status_code == 401


def test_link_token_update_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/v1/plaid/link-token/update", json={"bank_id": str(uuid.uuid4())}
    )
    assert response.status_code == 401


def test_link_token_update_404_for_nonexistent_bank(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("reauth-tester@example.com")

    response = client.post(
        "/api/v1/plaid/link-token/update",
        headers={"Authorization": f"Bearer {token}"},
        json={"bank_id": str(uuid.uuid4())},
    )

    assert response.status_code == 404
