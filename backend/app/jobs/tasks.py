from app.celery_app import celery_app


@celery_app.task(name="jobs.ping")
def ping() -> str:
    """Trivial task proving the worker/broker/backend wiring end to end (ROADMAP 3.1)."""
    return "pong"
