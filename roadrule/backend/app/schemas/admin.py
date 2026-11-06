from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


def normalize_admin_email(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Provide an administrator email address.")
    value = value.strip().lower()
    if not value.isascii():
        raise ValueError("Use an ASCII administrator email address.")
    return value


class AdminLoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    email: EmailStr = Field(max_length=254)
    password: SecretStr = Field(min_length=1, max_length=256)
    _email = field_validator("email", mode="before")(normalize_admin_email)


class AdminIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    fullName: str
    email: str
    role: Literal["ADMIN"] = "ADMIN"
    expiresAt: datetime


class DashboardSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    totalStudents: int
    totalExamAttempts: None = None
    passedExams: None = None
    failedExams: None = None
    totalVerifiedRevenue: None = None
    activePromoCodes: None = None
