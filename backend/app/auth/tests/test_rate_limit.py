from fastapi.testclient import TestClient

from app.core import rate_limit


def test_sixth_login_attempt_in_window_is_rate_limited(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "ratelimited@example.com", "password": "correct-password", "name": "RL"},
    )
    payload = {"email": "ratelimited@example.com", "password": "wrong-password"}

    for _ in range(5):
        resp = client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 401

    sixth = client.post("/api/v1/auth/login", json=payload)
    assert sixth.status_code == 429


def test_login_rate_limit_resets_after_window(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "resets@example.com", "password": "correct-password", "name": "R"},
    )
    key = "ratelimit:login:testclient:resets@example.com"

    for _ in range(5):
        client.post("/api/v1/auth/login", json={"email": "resets@example.com", "password": "wrong"})
    blocked = client.post(
        "/api/v1/auth/login", json={"email": "resets@example.com", "password": "wrong"}
    )
    assert blocked.status_code == 429

    # Simulate the window elapsing by clearing the counter directly.
    rate_limit.get_redis().delete(key)

    after_reset = client.post(
        "/api/v1/auth/login", json={"email": "resets@example.com", "password": "correct-password"}
    )
    assert after_reset.status_code == 200


def test_register_rate_limited_per_ip(client: TestClient) -> None:
    for i in range(10):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": f"many{i}@example.com", "password": "correct-password", "name": "M"},
        )
        assert resp.status_code == 201

    eleventh = client.post(
        "/api/v1/auth/register",
        json={"email": "many-overflow@example.com", "password": "correct-password", "name": "M"},
    )
    assert eleventh.status_code == 429


def test_refresh_rate_limited_per_user(client: TestClient) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "refresher@example.com", "password": "correct-password", "name": "RF"},
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": "refresher@example.com", "password": "correct-password"},
    )

    for _ in range(30):
        resp = client.post("/api/v1/auth/refresh")
        assert resp.status_code == 200

    blocked = client.post("/api/v1/auth/refresh")
    assert blocked.status_code == 429
