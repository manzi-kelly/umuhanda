import re
import unicodedata
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def normalize_name(value: str) -> str:
    value = " ".join(unicodedata.normalize("NFC", value).split())
    separators = set(" ’'‐-")
    if not value or len(value) > 120:
        raise ValueError("Provide a full name of at most 120 characters.")
    previous_separator = True
    for character in value:
        if character in separators:
            if previous_separator:
                raise ValueError("Provide a valid full name.")
            previous_separator = True
        elif unicodedata.category(character).startswith("L"):
            previous_separator = False
        elif unicodedata.category(character).startswith("M") and not previous_separator:
            continue
        else:
            raise ValueError("Provide a valid full name.")
    if previous_separator:
        raise ValueError("Provide a valid full name.")
    return value


def normalize_phone(value: str) -> str:
    if not re.fullmatch(r"[+0-9\s()-]+", value, flags=re.ASCII):
        raise ValueError("Provide a valid Rwanda mobile number.")
    value = re.sub(r"[\s()-]", "", value, flags=re.ASCII)
    if value.startswith("+250"):
        value = value[4:]
    elif value.startswith("250"):
        value = value[3:]
    elif value.startswith("0"):
        value = value[1:]
    if not re.fullmatch(r"7[23789][0-9]{7}", value, flags=re.ASCII):
        raise ValueError("Provide a valid Rwanda mobile number.")
    return "+250" + value


def mask_phone(value: str) -> str:
    return value[:6] + "*****" + value[-2:]


class StudentSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    fullName: str = Field(min_length=1, max_length=240)
    phoneNumber: str = Field(min_length=1, max_length=30)

    _name = field_validator("fullName")(normalize_name)
    _phone = field_validator("phoneNumber")(normalize_phone)


class StudentSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    studentId: UUID
    sessionReference: UUID  # Informational identifier; not a credential.
    fullName: str
    maskedPhoneNumber: str
    expiresAt: datetime
    accessGranted: Literal[False] = False
