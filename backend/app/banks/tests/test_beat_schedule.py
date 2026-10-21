from app.banks.tasks import reconcile_removed_plaid_items_task
from app.celery_app import celery_app


def test_reconcile_task_is_registered() -> None:
    assert "banks.reconcile_removed_plaid_items" in celery_app.tasks


def test_beat_schedule_includes_the_reconcile_entry() -> None:
    schedule = celery_app.conf.beat_schedule
    tasks = {entry["task"] for entry in schedule.values()}
    assert "banks.reconcile_removed_plaid_items" in tasks
    for entry in schedule.values():
        assert entry["schedule"].total_seconds() > 0


def test_reconcile_task_runs_with_zero_removed_items_in_the_system() -> None:
    result = reconcile_removed_plaid_items_task.delay()
    assert result.get(timeout=10) is None
