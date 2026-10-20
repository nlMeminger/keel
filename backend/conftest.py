from collections.abc import Generator
from urllib.parse import urlsplit, urlunsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.core import rate_limit
from app.database import Base, get_db
from app.main import app


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
    """Recreate every table fresh for each test — isolation over speed, given the suite's size."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield


@pytest.fixture(autouse=True)
def _reset_redis() -> Generator[None, None, None]:
    """Flush rate-limit counters between tests, isolated from dev's Redis DB 0."""
    original_url = settings.redis_url
    settings.redis_url = _test_redis_url(original_url)
    rate_limit.get_redis().flushdb()
    yield
    settings.redis_url = original_url


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
