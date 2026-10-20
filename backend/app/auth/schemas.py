import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(min_length=1)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MeUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    timezone: str | None = None


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    timezone: str
    role: str
    status: str
    must_change_password: bool
    created_at: datetime


class AccessTokenData(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginResponseData(AccessTokenData):
    user: UserPublic


class SessionPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    last_used_at: datetime | None
    user_agent: str | None
    is_current: bool
