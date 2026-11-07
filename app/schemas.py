from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["applied", "interviewing", "offer", "rejected", "withdrawn"]
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterIn(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str


class ApplicationIn(BaseModel):
    company: str = Field(min_length=1, max_length=200)
    role_title: str = Field(min_length=1, max_length=200)
    status: Status = "applied"
    applied_on: date
    follow_up_on: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ApplicationPatch(BaseModel):
    """Only fields that are sent get changed. Sending null clears follow_up_on and notes."""

    company: str | None = Field(default=None, min_length=1, max_length=200)
    role_title: str | None = Field(default=None, min_length=1, max_length=200)
    status: Status | None = None
    applied_on: date | None = None
    follow_up_on: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company: str
    role_title: str
    status: str
    applied_on: date
    follow_up_on: date | None
    notes: str | None
