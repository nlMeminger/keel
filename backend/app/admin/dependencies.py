from fastapi import Depends

from app.auth.models import User
from app.core.errors import AppError
from app.dependencies import get_current_user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Separate trust boundary from ownership-based access (SPEC.md §6) — every /admin/*
    route depends on this instead of get_current_user directly, so a non-admin's otherwise
    valid token still gets 403 here regardless of whose data it would otherwise own."""
    if user.role != "admin":
        raise AppError(403, "admin_required", "Admin access required.")
    return user
