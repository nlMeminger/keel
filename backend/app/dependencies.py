from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.models import User
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.database import get_db

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the acting user from the verified JWT.

    Every write route's ownership check starts here — never trust a client-supplied
    user_id, this is the only source of truth for "who is calling."
    """
    if credentials is None:
        raise AppError(401, "unauthorized", "Missing or invalid Authorization header.")
    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id)
    if user is None or user.status != "active":
        raise AppError(401, "unauthorized", "Invalid or expired token.")
    return user
