import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session as DbSession

from app.admin.schemas import AdminUserPublic
from app.auth.models import User
from app.auth.service import revoke_other_sessions
from app.banks.models import Bank, PlaidItem
from app.banks.service import remove_plaid_item
from app.core.errors import AppError
from app.core.plaid_client import calls_this_month
from app.core.security import generate_opaque_token, hash_password


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
