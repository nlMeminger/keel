import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.jobs.models import Job
from app.sync.schemas import JobProgress

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


class AdminJobPublic(BaseModel):
    """GET /admin/jobs (API_SPEC.md §18) — same Job row JobStatus (app.sync.schemas)
    renders for a per-user poll, plus `owner_id` since this view spans every user."""

    id: uuid.UUID
    type: str
    status: str
    owner_id: uuid.UUID | None
    progress: JobProgress | None
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_job(cls, job: Job) -> "AdminJobPublic":
        progress = None
        if job.progress_current is not None and job.progress_total is not None:
            progress = JobProgress(current=job.progress_current, total=job.progress_total)
        return cls(
            id=job.id,
            type=job.type,
            status=job.status,
            owner_id=job.owner_id,
            progress=progress,
            result=job.result,
            error=job.error,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )


class LogEntryPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    level: str
    logger_name: str
    message: str
    created_at: datetime


class SyncAllTriggerResponseData(BaseModel):
    job_id: uuid.UUID


class BankHealthCheckResponseData(BaseModel):
    bank_id: uuid.UUID
    health: str


class BeatScheduleEntry(BaseModel):
    task: str
    schedule_seconds: float


class AdminConfigResponseData(BaseModel):
    environment: str
    cors_origins: list[str]
    beat_schedule: list[BeatScheduleEntry]


PlaidStatsGroupBy = Literal["user", "endpoint", "month"]


class PlaidApiStatRow(BaseModel):
    """One aggregated row from GET /admin/plaid/api-stats — `group` is the stringified
    group key: a user id, an endpoint name, or a "YYYY-MM" month, depending on `group_by`."""

    group: str
    count: int


class PlaidApiCallPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    endpoint: str
    status: str
    error_code: str | None
    created_at: datetime


def _validate_scopes(scopes: list[str]) -> list[str]:
    """API_SPEC.md §18: scopes is exactly `["read"]` or `["read","write"]` — never `["write"]`
    alone, never duplicates, never any other value."""
    if set(scopes) not in ({"read"}, {"read", "write"}) or len(scopes) != len(set(scopes)):
        raise ValueError('scopes must be exactly ["read"] or ["read", "write"]')
    return scopes


class AdminApiTokenCreateRequest(BaseModel):
    user_id: uuid.UUID
    label: str = Field(min_length=1)
    scopes: list[Literal["read", "write"]]
    expires_at: datetime | None = None

    _validate_scopes = field_validator("scopes")(_validate_scopes)


class AdminApiTokenUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1)
    expires_at: datetime | None = None


class AdminApiTokenPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    label: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


class AdminApiTokenCreateResponseData(BaseModel):
    token: AdminApiTokenPublic
    secret: str
