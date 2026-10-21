from app.celery_app import celery_app
from app.sync.tasks import scheduled_sync_balances_task, scheduled_sync_transactions_task


def test_scheduled_sync_tasks_are_registered() -> None:
    assert "sync.scheduled_transactions" in celery_app.tasks
    assert "sync.scheduled_balances" in celery_app.tasks


def test_beat_schedule_includes_both_scheduled_sync_entries() -> None:
    schedule = celery_app.conf.beat_schedule
    tasks = {entry["task"] for entry in schedule.values()}
    assert "sync.scheduled_transactions" in tasks
    assert "sync.scheduled_balances" in tasks
    for entry in schedule.values():
        assert entry["schedule"].total_seconds() > 0


def test_scheduled_tasks_run_with_zero_banks_in_the_system() -> None:
    # Trivial case (no banks linked anywhere yet) still completes and creates a system job.
    result = scheduled_sync_transactions_task.delay()
    assert result.get(timeout=10) is None

    result = scheduled_sync_balances_task.delay()
    assert result.get(timeout=10) is None
