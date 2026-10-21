import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

UserRole = Literal["user", "admin"]
UserStatus = Literal["active", "suspended"]


class AdminUserPublic(BaseModel):
    """Account metadata only (API_SPEC.md §18) — never a user's transactions/balances/other
    financial data, which stays outside the admin surface entirely (CLAUDE.md Don't-do-this)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    role: str
    status: str
    plaid_enabled: bool
    plaid_monthly_call_limit: int | None
    plaid_calls_this_month: int
    must_change_password: bool
    linked_bank_count: int
    created_at: datetime
    last_login_at: datetime | None


class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1)
    role: UserRole = "user"
    password: str | None = Field(default=None, min_length=8)


class AdminUserCreateResponseData(BaseModel):
    user: AdminUserPublic
    initial_password: str


class AdminUserUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    email: EmailStr | None = None
    timezone: str | None = None
    role: UserRole | None = None
    status: UserStatus | None = None


class AdminResetPasswordRequest(BaseModel):
    password: str | None = Field(default=None, min_length=8)


class AdminResetPasswordResponseData(BaseModel):
    # Only populated when `password` was omitted from the request and the backend had to
    # generate one — an admin-supplied password is never echoed back.
    temporary_password: str | None


class AdminPlaidAccessUpdateRequest(BaseModel):
    enabled: bool
    monthly_call_limit: int | None = None


class AdminUserDeleteRequest(BaseModel):
    confirm: bool
