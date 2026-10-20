"""One-time first-admin creation. Run manually at deploy time, never exposed as an API route
(see API_SPEC.md §18 — a "first user to register becomes admin" rule is racy and exploitable).

Usage:
    uv run python scripts/bootstrap_admin.py --email admin@example.com --name "Admin"
    uv run python scripts/bootstrap_admin.py --email admin@example.com --name "Admin" \
        --password "..."

If --password is omitted, a random one is generated and printed once — it is never logged
or stored anywhere else, so capture it immediately.
"""

import argparse
import secrets
import sys

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.auth.models import User
from app.core.security import hash_password
from app.database import SessionLocal


class BootstrapAdminError(Exception):
    pass


def bootstrap_admin(
    db: DbSession, email: str, name: str, password: str | None
) -> tuple[User, str | None]:
    """Creates the first admin. Returns (user, generated_password or None).

    Raises BootstrapAdminError if an admin already exists or the email is taken —
    callers decide how to surface that (CLI exit code vs. a test assertion).
    """
    existing_admin = db.scalar(select(User).where(User.role == "admin"))
    if existing_admin is not None:
        raise BootstrapAdminError(f"An admin already exists ({existing_admin.email}).")

    if db.scalar(select(User).where(User.email == email)) is not None:
        raise BootstrapAdminError(f"A user with email {email} already exists.")

    generated_password = None if password is not None else secrets.token_urlsafe(16)
    raw_password = password or generated_password
    assert raw_password is not None

    admin = User(email=email, password_hash=hash_password(raw_password), name=name, role="admin")
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin, generated_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the first admin user.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", default=None, help="Omit to auto-generate one.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        admin, generated_password = bootstrap_admin(db, args.email, args.name, args.password)
    except BootstrapAdminError as exc:
        print(f"Refusing to proceed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

    print(f"Created admin user: {admin.email}")
    if generated_password is not None:
        print(f"Generated password (shown once, not stored anywhere): {generated_password}")


if __name__ == "__main__":
    main()
