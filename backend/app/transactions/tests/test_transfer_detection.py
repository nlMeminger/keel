import uuid
from collections.abc import Callable

from fastapi.testclient import TestClient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_account(client: TestClient, token: str, name: str = "Checking") -> str:
    resp = client.post(
        "/api/v1/accounts",
        json={"name": name, "account_type": "checking", "balance": "0"},
        headers=_auth_headers(token),
    )
    return str(resp.json()["data"]["id"])


def _create_txn(
    client: TestClient, token: str, account_id: str, amount: str, txn_date: str, desc: str = "x"
) -> dict[str, object]:
    resp = client.post(
        "/api/v1/transactions",
        json={"account_id": account_id, "amount": amount, "description": desc, "date": txn_date},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert isinstance(data, dict)
    return data


def test_opposite_sign_same_amount_within_one_business_day_suggested(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("transfer-1day@example.com")
    checking = _create_account(client, token, "Checking")
    savings = _create_account(client, token, "Savings")

    out_txn = _create_txn(client, token, checking, "-100.00", "2026-03-04")  # Wednesday
    in_txn = _create_txn(client, token, savings, "100.00", "2026-03-05")  # Thursday

    assert in_txn["transfer_status"] == "suggested"
    assert in_txn["paired_transaction_id"] == out_txn["id"]

    get_resp = client.get(f"/api/v1/transactions/{out_txn['id']}", headers=_auth_headers(token))
    refreshed_out = get_resp.json()["data"]
    assert refreshed_out["transfer_status"] == "suggested"
    assert refreshed_out["paired_transaction_id"] == in_txn["id"]


def test_opposite_sign_same_amount_within_two_business_days_suggested(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("transfer-2day@example.com")
    checking = _create_account(client, token, "Checking")
    savings = _create_account(client, token, "Savings")

    _create_txn(client, token, checking, "-50.00", "2026-03-02")  # Monday
    in_txn = _create_txn(client, token, savings, "50.00", "2026-03-04")  # Wednesday (2 biz days)

    assert in_txn["transfer_status"] == "suggested"


def test_three_business_days_apart_does_not_match(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("transfer-3day@example.com")
    checking = _create_account(client, token, "Checking")
    savings = _create_account(client, token, "Savings")

    _create_txn(client, token, checking, "-50.00", "2026-03-02")  # Monday
    in_txn = _create_txn(client, token, savings, "50.00", "2026-03-05")  # Thursday (3 biz days)

    assert in_txn["transfer_status"] == "none"
    assert in_txn["paired_transaction_id"] is None


def test_same_sign_amounts_never_match(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("transfer-samesign@example.com")
    checking = _create_account(client, token, "Checking")
    savings = _create_account(client, token, "Savings")

    _create_txn(client, token, checking, "-50.00", "2026-03-04")
    in_txn = _create_txn(client, token, savings, "-50.00", "2026-03-04")

    assert in_txn["transfer_status"] == "none"


def test_different_users_account_is_never_a_candidate_even_on_coincidental_match(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    owner_token, _owner_id = register_and_login("transfer-owner@example.com")
    owner_account = _create_account(client, owner_token, "Owner checking")
    _create_txn(client, owner_token, owner_account, "-75.00", "2026-03-04")

    other_token, _other_id = register_and_login("transfer-other@example.com")
    other_account = _create_account(client, other_token, "Other checking")
    other_txn = _create_txn(client, other_token, other_account, "75.00", "2026-03-04")

    assert other_txn["transfer_status"] == "none"
    assert other_txn["paired_transaction_id"] is None


def test_confirm_sets_is_transfer_and_transfer_category_on_both_sides(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("transfer-confirm@example.com")
    checking = _create_account(client, token, "Checking")
    savings = _create_account(client, token, "Savings")

    out_txn = _create_txn(client, token, checking, "-200.00", "2026-03-04")
    in_txn = _create_txn(client, token, savings, "200.00", "2026-03-04")

    confirm_resp = client.patch(
        f"/api/v1/transactions/{in_txn['id']}",
        json={"transfer_status": "confirmed"},
        headers=_auth_headers(token),
    )
    assert confirm_resp.status_code == 200
    confirmed = confirm_resp.json()["data"]
    assert confirmed["is_transfer"] is True
    assert confirmed["transfer_status"] == "confirmed"
    transfer_category_id = confirmed["category_id"]
    assert transfer_category_id is not None

    other_side = client.get(
        f"/api/v1/transactions/{out_txn['id']}", headers=_auth_headers(token)
    ).json()["data"]
    assert other_side["is_transfer"] is True
    assert other_side["transfer_status"] == "confirmed"
    assert other_side["category_id"] == transfer_category_id


def test_reject_clears_both_sides_and_is_never_re_suggested(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("transfer-reject@example.com")
    checking = _create_account(client, token, "Checking")
    savings = _create_account(client, token, "Savings")

    out_txn = _create_txn(client, token, checking, "-60.00", "2026-03-04")
    in_txn = _create_txn(client, token, savings, "60.00", "2026-03-04")

    reject_resp = client.patch(
        f"/api/v1/transactions/{in_txn['id']}",
        json={"transfer_status": "rejected"},
        headers=_auth_headers(token),
    )
    assert reject_resp.json()["data"]["transfer_status"] == "rejected"
    assert reject_resp.json()["data"]["paired_transaction_id"] is None

    other_side = client.get(
        f"/api/v1/transactions/{out_txn['id']}", headers=_auth_headers(token)
    ).json()["data"]
    assert other_side["transfer_status"] == "rejected"
    assert other_side["paired_transaction_id"] is None

    # A brand-new identical-shaped transaction must not re-pair with either rejected side.
    third = _create_txn(client, token, savings, "60.00", "2026-03-04")
    assert third["transfer_status"] == "none"


def test_patch_transfer_status_without_pending_suggestion_returns_409(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("transfer-no-suggestion@example.com")
    checking = _create_account(client, token, "Checking")
    txn = _create_txn(client, token, checking, "-10.00", "2026-03-04")

    resp = client.patch(
        f"/api/v1/transactions/{txn['id']}",
        json={"transfer_status": "confirmed"},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 409


def test_deleting_one_side_of_a_suggested_pair_resets_the_other_side(
    client: TestClient, register_and_login: Callable[[str], tuple[str, uuid.UUID]]
) -> None:
    token, _user_id = register_and_login("transfer-delete@example.com")
    checking = _create_account(client, token, "Checking")
    savings = _create_account(client, token, "Savings")

    out_txn = _create_txn(client, token, checking, "-30.00", "2026-03-04")
    in_txn = _create_txn(client, token, savings, "30.00", "2026-03-04")
    assert in_txn["transfer_status"] == "suggested"

    client.delete(f"/api/v1/transactions/{out_txn['id']}", headers=_auth_headers(token))

    remaining = client.get(
        f"/api/v1/transactions/{in_txn['id']}", headers=_auth_headers(token)
    ).json()["data"]
    assert remaining["transfer_status"] == "none"
    assert remaining["paired_transaction_id"] is None
