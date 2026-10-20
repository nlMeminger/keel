from app.celery_app import celery_app
from app.jobs.tasks import ping


def test_ping_task_is_registered() -> None:
    assert "jobs.ping" in celery_app.tasks


def test_ping_task_executes_and_result_is_retrievable() -> None:
    result = ping.delay()
    assert result.get(timeout=10) == "pong"
