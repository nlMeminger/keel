import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session as DbSession

from app.admin.models import AdminAuditLog, ApiToken, LogEntry
from app.admin.schemas import (
    AdminConfigResponseData,
    AdminUserPublic,
    BeatScheduleEntry,
    PlaidApiStatRow,
    PlaidStatsGroupBy,
)
from app.auth.models import User
from app.auth.service import revoke_other_sessions
from app.banks import service as banks_service
from app.banks.models import Bank, PlaidAPICall, PlaidItem
from app.banks.service import remove_plaid_item
from app.banks.tasks import reconcile_removed_plaid_items_task
from app.celery_app import celery_app
from app.config import settings
from app.core.errors import AppError
from app.core.plaid_client import calls_this_month
from app.core.security import generate_opaque_token, hash_password, hash_token
from app.jobs.models import Job
from app.jobs.service import create_job
from app.sync.tasks import scheduled_sync_balances_task, scheduled_sync_transactions_task


def list_users_stmt(role: str | None, status: str | None) -> Select[User]:
    stmt = select(User).order_by(User.created_at)
    if role is not None:
        stmt = stmt.where(User.role == role)
    if status is not None:
        stmt = stmt.where(User.status == status)
    return stmt


def get_user(db: DbSession, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, "not_found", "User not found.")
    return user


def count_linked_banks(db: DbSession, user_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(Bank).where(Bank.owner_id == user_id)
    return db.scalar(stmt) or 0


def admin_count(db: DbSession) -> int:
    stmt = select(func.count()).select_from(User).where(User.role == "admin")
    return db.scalar(stmt) or 0


def to_public(db: DbSession, user: User) -> AdminUserPublic:
    return AdminUserPublic(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        status=user.status,
        plaid_enabled=user.plaid_enabled,
        plaid_monthly_call_limit=user.plaid_monthly_call_limit,
        plaid_calls_this_month=calls_this_month(db, user.id),
        must_change_password=user.must_change_password,
        linked_bank_count=count_linked_banks(db, user.id),
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def create_user(
    db: DbSession, email: str, name: str, role: str, password: str | None
) -> tuple[User, str]:
    """POST /admin/users (API_SPEC.md §18) — provisions an account directly, bypassing
    self-registration. Initial password follows the same shape as reset_password below:
    admin-supplied or freshly generated, forcing a change on first login either way."""
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise AppError(409, "email_taken", "An account with this email already exists.")
    initial_password = password or generate_opaque_token()
    user = User(
        email=email,
        name=name,
        role=role,
        password_hash=hash_password(initial_password),
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, initial_password


def _reject_if_last_admin(db: DbSession, user: User, action: str) -> None:
    if user.role == "admin" and admin_count(db) <= 1:
        raise AppError(409, "last_admin", f"Cannot {action} the last remaining admin.")


def update_user(
    db: DbSession,
    user: User,
    name: str | None,
    email: str | None,
    timezone: str | None,
    role: str | None,
    status: str | None,
) -> User:
    if role is not None and role != user.role:
        _reject_if_last_admin(db, user, "demote")
    if status is not None and status != "active":
        _reject_if_last_admin(db, user, "suspend")

    if name is not None:
        user.name = name
    if email is not None:
        user.email = email
    if timezone is not None:
        user.timezone = timezone
    if role is not None:
        user.role = role
    if status is not None:
        user.status = status
    db.commit()
    db.refresh(user)
    return user


def reset_password(db: DbSession, user: User, password: str | None) -> str | None:
    """POST /admin/users/{id}/reset-password (API_SPEC.md §18) — forces must_change_password
    and revokes every active session, same as a detected compromise would. Returns the
    generated password only when the admin didn't supply one; an admin-supplied value is
    never echoed back."""
    generated = password is None
    new_password = password or generate_opaque_token()
    user.password_hash = hash_password(new_password)
    user.must_change_password = True
    db.commit()
    revoke_other_sessions(db, user, keep_token_hash=None)
    return new_password if generated else None


def revoke_sessions(db: DbSession, user: User) -> None:
    revoke_other_sessions(db, user, keep_token_hash=None)


def update_plaid_access(
    db: DbSession, user: User, enabled: bool, monthly_call_limit: int | None
) -> User:
    user.plaid_enabled = enabled
    user.plaid_monthly_call_limit = monthly_call_limit
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: DbSession, user: User, confirm: bool) -> None:
    """DELETE /admin/users/{id} (API_SPEC.md §18) — irreversible, so requires an explicit
    confirm flag. Removes every one of the user's Plaid items first (same Plaid-side cleanup
    as a self-service unlink) so nothing keeps accruing Plaid API cost once the user is gone;
    not gated on plaid_enabled/ensure_plaid_enabled the way self-service unlink is, since this
    cleanup must still run for a user whose Plaid access an admin already disabled."""
    if not confirm:
        raise AppError(400, "confirmation_required", "Deleting a user requires confirm=true.")
    _reject_if_last_admin(db, user, "delete")

    banks = db.scalars(select(Bank).where(Bank.owner_id == user.id)).all()
    for bank in banks:
        item = db.get(PlaidItem, bank.plaid_item_id)
        assert item is not None
        remove_plaid_item(db, user.id, item)

    db.delete(user)
    db.commit()


def list_jobs_stmt(job_type: str | None, status: str | None) -> Select[Job]:
    stmt = select(Job).order_by(Job.created_at.desc())
    if job_type is not None:
        stmt = stmt.where(Job.type == job_type)
    if status is not None:
        stmt = stmt.where(Job.status == status)
    return stmt


def list_logs_stmt(
    level: str | None, date_from: datetime | None, date_to: datetime | None
) -> Select[LogEntry]:
    stmt = select(LogEntry).order_by(LogEntry.created_at.desc())
    if level is not None:
        stmt = stmt.where(LogEntry.level == level.upper())
    if date_from is not None:
        stmt = stmt.where(LogEntry.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(LogEntry.created_at <= date_to)
    return stmt


def trigger_sync_all_transactions(db: DbSession) -> Job:
    """POST /admin/sync/transactions (API_SPEC.md §18) — force-triggers the same system-wide
    sync Celery beat runs on a schedule, distinct from a user's own per-bank/per-user
    `/sync/transactions` (§16). Creates the Job here so the response carries an id to poll
    immediately; scheduled_sync_transactions_task reuses the same body either way."""
    job = create_job(db, "transaction_sync", owner_id=None)
    scheduled_sync_transactions_task.delay(job_id=str(job.id))
    return job


def trigger_sync_all_balances(db: DbSession) -> Job:
    job = create_job(db, "balance_sync", owner_id=None)
    scheduled_sync_balances_task.delay(job_id=str(job.id))
    return job


def trigger_reconcile_items(db: DbSession) -> Job:
    job = create_job(db, "plaid_item_reconciliation", owner_id=None)
    reconcile_removed_plaid_items_task.delay(job_id=str(job.id))
    return job


def check_bank_health(db: DbSession, bank_id: uuid.UUID) -> tuple[uuid.UUID, str]:
    bank, item = banks_service.get_bank_any_owner(db, bank_id)
    health = banks_service.check_bank_health(db, bank, item)
    return bank.id, health


def get_config() -> AdminConfigResponseData:
    """GET /admin/config (API_SPEC.md §18) — non-secret operational config only. Infra
    secrets (DB password, Plaid secret, JWT signing key) are never read from `settings`
    here, by construction — this function doesn't import anything that would expose them."""
    beat_schedule = [
        BeatScheduleEntry(task=entry["task"], schedule_seconds=entry["schedule"].total_seconds())
        for entry in celery_app.conf.beat_schedule.values()
    ]
    return AdminConfigResponseData(
        environment=settings.environment,
        cors_origins=settings.cors_origins,
        beat_schedule=beat_schedule,
    )


def _group_column(group_by: PlaidStatsGroupBy) -> Any:
    # Any: InstrumentedAttribute and func.to_char(...) share no common SQLAlchemy stub type
    # narrower than this that both select()/group_by() below accept.
    if group_by == "user":
        return PlaidAPICall.user_id
    if group_by == "endpoint":
        return PlaidAPICall.endpoint
    return func.to_char(PlaidAPICall.created_at, "YYYY-MM")


def plaid_api_stats(
    db: DbSession,
    group_by: PlaidStatsGroupBy,
    user_id: uuid.UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[PlaidApiStatRow]:
    """GET /admin/plaid/api-stats (API_SPEC.md §18) — call counts only, never a hardcoded
    dollar estimate (Plaid's per-endpoint pricing varies and changes). One row per distinct
    group value, never a combined total across groups."""
    group_col = _group_column(group_by)
    stmt = select(group_col, func.count()).group_by(group_col)
    if user_id is not None:
        stmt = stmt.where(PlaidAPICall.user_id == user_id)
    if date_from is not None:
        stmt = stmt.where(PlaidAPICall.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(PlaidAPICall.created_at <= date_to)
    rows = db.execute(stmt).all()
    return [PlaidApiStatRow(group=str(key), count=count) for key, count in rows]


def list_plaid_calls_stmt(
    user_id: uuid.UUID | None,
    endpoint: str | None,
    status: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> Select[PlaidAPICall]:
    stmt = select(PlaidAPICall).order_by(PlaidAPICall.created_at.desc())
    if user_id is not None:
        stmt = stmt.where(PlaidAPICall.user_id == user_id)
    if endpoint is not None:
        stmt = stmt.where(PlaidAPICall.endpoint == endpoint)
    if status is not None:
        stmt = stmt.where(PlaidAPICall.status == status)
    if date_from is not None:
        stmt = stmt.where(PlaidAPICall.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(PlaidAPICall.created_at <= date_to)
    return stmt


def list_api_tokens_stmt() -> Select[ApiToken]:
    return select(ApiToken).order_by(ApiToken.created_at.desc())


def get_api_token(db: DbSession, token_id: uuid.UUID) -> ApiToken:
    token = db.get(ApiToken, token_id)
    if token is None:
        raise AppError(404, "not_found", "API token not found.")
    return token


def create_api_token(
    db: DbSession,
    admin: User,
    user_id: uuid.UUID,
    label: str,
    scopes: list[str],
    expires_at: datetime | None,
) -> tuple[ApiToken, str]:
    """POST /admin/api-tokens (API_SPEC.md §18) — binds the token to `user_id`; requests
    authenticated with it act as that user, never with admin-level access regardless of
    who issued it. The raw secret is returned here, once, and never stored or shown again."""
    if db.get(User, user_id) is None:
        raise AppError(404, "not_found", "User not found.")
    secret = generate_opaque_token()
    token = ApiToken(
        user_id=user_id,
        created_by_admin_id=admin.id,
        label=label,
        scopes=scopes,
        token_hash=hash_token(secret),
        expires_at=expires_at,
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token, secret


def update_api_token(
    db: DbSession, token: ApiToken, label: str | None, expires_at: datetime | None
) -> ApiToken:
    """PATCH /admin/api-tokens/{id} — renames the label or changes `expires_at` only; not
    secret rotation (revoke + reissue is the only way to change the secret itself)."""
    if label is not None:
        token.label = label
    if expires_at is not None:
        token.expires_at = expires_at
    db.commit()
    db.refresh(token)
    return token


def revoke_api_token(db: DbSession, token: ApiToken) -> None:
    if token.revoked_at is None:
        token.revoked_at = datetime.now(UTC)
        db.commit()


def list_audit_log_stmt(
    admin_user_id: uuid.UUID | None,
    action: str | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> Select[AdminAuditLog]:
    stmt = select(AdminAuditLog).order_by(AdminAuditLog.created_at.desc())
    if admin_user_id is not None:
        stmt = stmt.where(AdminAuditLog.admin_user_id == admin_user_id)
    if action is not None:
        stmt = stmt.where(AdminAuditLog.action == action)
    if date_from is not None:
        stmt = stmt.where(AdminAuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AdminAuditLog.created_at <= date_to)
    return stmt
