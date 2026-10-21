from datetime import timedelta

from celery import Celery

from app.config import settings

celery_app = Celery(
    "moneyapp",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.jobs.tasks", "app.category_rules.tasks", "app.sync.tasks", "app.banks.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# Plaid webhooks are the primary trigger for real-time updates (SPEC.md §3) — these cover
# the scheduled/background path for banks that don't fire one. Balances are cheap (one
# /accounts/get call per bank) so they run hourly; transaction sync is heavier and Plaid's
# own SYNC_UPDATES_AVAILABLE webhook (7.8) already covers the common case, so every 6 hours
# is enough of a backstop.
celery_app.conf.beat_schedule = {
    "sync-transactions": {
        "task": "sync.scheduled_transactions",
        "schedule": timedelta(hours=6),
    },
    "sync-balances": {
        "task": "sync.scheduled_balances",
        "schedule": timedelta(hours=1),
    },
    # Ghost-item check's scheduled half (ROADMAP 7.11) — the webhook-side check only catches
    # an item that keeps sending webhooks; this catches one that's gone quiet instead. Daily
    # is enough: a stale removed item accruing Plaid cost is a slow leak, not an emergency.
    "reconcile-removed-plaid-items": {
        "task": "banks.reconcile_removed_plaid_items",
        "schedule": timedelta(hours=24),
    },
}
