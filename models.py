from datetime import datetime
from enum import Enum
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# +91 followed by exactly 10 digits, or standard E.164 (+[country 1-9][6-14 more digits])
_IN_PHONE_RE = re.compile(r"^\+91\d{10}$")
_E164_PHONE_RE = re.compile(r"^\+[1-9]\d{6,14}$")
_STRIP_SEPARATORS_RE = re.compile(r"[\s\-()]+")


class SMSStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"


class SendSMSRequest(BaseModel):
    to: str = Field(..., description="Recipient phone number in +91 or E.164 format")
    message: str = Field(..., min_length=1, max_length=1600, description="SMS body text")
    priority: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Dispatch priority from 1 (lowest) to 5 (highest)",
    )

    @field_validator("to")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        normalized = _STRIP_SEPARATORS_RE.sub("", value.strip())
        if normalized.startswith("+91"):
            if not _IN_PHONE_RE.match(normalized):
                raise ValueError(
                    "Invalid +91 phone number; expected '+91' followed by exactly 10 digits"
                )
            return normalized
        if not _E164_PHONE_RE.match(normalized):
            raise ValueError(
                "Invalid phone number; must be in +91 or E.164 format (e.g. +919876543210 or +14155552671)"
            )
        return normalized

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty or whitespace-only")
        return cleaned


class SendSMSResponse(BaseModel):
    message_id: str
    status: SMSStatus
    device_online: bool
    queued_at: datetime


class SMSStatusResponse(BaseModel):
    message_id: str
    project_id: str
    project_name: str
    to: str
    message: str
    priority: int
    status: SMSStatus
    retry_count: int
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None = None


class QueueCounts(BaseModel):
    pending: int
    processing: int
    sent: int
    failed: int
    total: int


class AdminLogsResponse(BaseModel):
    device_online: bool
    counts: QueueCounts
    logs: list[SMSStatusResponse]


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    rate_limit_per_min: int = Field(default=60, ge=1, le=10000)
    is_active: bool = Field(default=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Project name cannot be empty")
        return cleaned


class ProjectResponse(BaseModel):
    id: str
    name: str
    api_key: str
    is_active: bool
    rate_limit_per_min: int
    created_at: datetime


class DevicePushPayload(BaseModel):
    message_id: str
    to: str
    message: str


class DeviceAckPayload(BaseModel):
    message_id: str
    status: Literal["sent", "failed"]
    error: str | None = None
