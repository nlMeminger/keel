import uuid
from collections.abc import Callable, Generator
from urllib.parse import urlsplit, urlunsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.database as database_module
from app.categories.seed import seed_categories
from app.celery_app import celery_app
from app.config import settings
from app.core import rate_limit
from app.database import Base, get_db
from app.main import app

# Tests never depend on a separately running Celery worker process (CI doesn't start one) —
# run tasks synchronously, in-process, instead.
celery_app.conf.task_always_eager = True
celery_app.conf.task_eager_propagates = True


def _test_database_url(base_url: str) -> str:
    """Point at a `_test`-suffixed database on the same server, without disturbing credentials."""
    parts = urlsplit(base_url)
    test_path = f"{parts.path}_test"
    return urlunsplit((parts.scheme, parts.netloc, test_path, parts.query, parts.fragment))


def _test_redis_url(base_url: str) -> str:
    """Point at a different logical Redis DB (1, not dev's 0) so rate-limit counters don't leak."""
    parts = urlsplit(base_url)
    return urlunsplit((parts.scheme, parts.netloc, "/1", parts.query, parts.fragment))


test_engine = create_engine(_test_database_url(settings.database_url))
TestSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def _reset_schema() -> Generator[None, None, None]:
    """Recreate every table fresh for each test — isolation over speed, given the suite's size.

    Schema comes from create_all(), not `alembic upgrade head`, so seed data (system
    categories) can't live only inside the migration body — it's re-applied here too.
    """
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        seed_categories(session)
    finally:
        session.close()
    yield


@pytest.fixture(autouse=True)
def _reset_redis() -> Generator[None, None, None]:
    """Flush rate-limit counters between tests, isolated from dev's Redis DB 0."""
    original_url = settings.redis_url
    settings.redis_url = _test_redis_url(original_url)
    rate_limit.get_redis().flushdb()
    yield
    settings.redis_url = original_url


@pytest.fixture(autouse=True)
def _reset_job_database_session() -> Generator[None, None, None]:
    """Celery tasks instantiate a DB session directly (no FastAPI dependency to override) —
    eagerly-run tasks during tests (task_always_eager above) must still resolve to the test
    database, not the real one. Task modules reference `database_module.SessionLocal` at call
    time, rather than importing the name directly, specifically so this patch takes effect."""
    original = database_module.SessionLocal
    database_module.SessionLocal = TestSessionLocal
    yield
    database_module.SessionLocal = original


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def register_and_login(client: TestClient) -> Callable[[str], tuple[str, uuid.UUID]]:
    """Registers+logs in a fresh user, returning (access_token, user_id) — the standard way
    every resource's ownership tests get a second, independent caller to test against."""

    def _do(email: str) -> tuple[str, uuid.UUID]:
        client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "correct-password", "name": "Tester"},
        )
        login = client.post(
            "/api/v1/auth/login", json={"email": email, "password": "correct-password"}
        )
        data = login.json()["data"]
        return data["access_token"], uuid.UUID(data["user"]["id"])

    return _do
