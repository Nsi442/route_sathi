"""Report, validation, priority and CSV-import schemas."""

from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel, Field, field_validator

from backend.core.constants import (
    ISSUE_TYPES,
    PRIORITIES,
    REPORT_STATUSES,
    SEVERITIES,
    VALIDATION_STATUSES,
    normalise_issue_type,
    title_match,
)
from backend.schemas.common import ORMModel


class ReportCreate(BaseModel):
    """Body of ``POST /api/user/reports`` when sent as JSON.

    The same fields are accepted as ``multipart/form-data`` when a photo is
    attached; see the router for the form variant.
    """

    issue_type: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    description: str | None = Field(default=None, max_length=2000)
    severity: str
    location_text: str | None = Field(default=None, max_length=300)
    timestamp: dt.datetime | None = None

    @field_validator("issue_type")
    @classmethod
    def _issue(cls, value: str) -> str:
        matched = normalise_issue_type(value)
        if not matched:
            raise ValueError(f"issue_type must be one of {', '.join(ISSUE_TYPES)}")
        return matched

    @field_validator("severity")
    @classmethod
    def _severity(cls, value: str) -> str:
        matched = title_match(value, SEVERITIES)
        if not matched:
            raise ValueError(f"severity must be one of {', '.join(SEVERITIES)}")
        return matched


class TaskBrief(BaseModel):
    task_id: str
    assigned_team: str
    status: str
    assigned_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    verified_at: dt.datetime | None = None
    maintenance_notes: str | None = None
    has_resolution_image: bool = False


class ReportOut(ORMModel):
    id: int
    report_id: str
    user_id: str
    issue_type: str
    location_text: str | None = None
    latitude: float
    longitude: float
    description: str | None = None
    severity: str
    image_url: str | None = None
    has_image: bool = False
    timestamp: dt.datetime
    validation_status: str
    validated_by: str | None = None
    validated_at: dt.datetime | None = None
    predicted_priority: str | None = None
    prediction_confidence: float | None = None
    final_priority: str | None = None
    priority_confirmed_by: str | None = None
    priority_confirmed_at: dt.datetime | None = None
    status: str
    source: str | None = None
    created_at: dt.datetime
    updated_at: dt.datetime
    reporter_name: str | None = None
    task: TaskBrief | None = None


class ReportMapPin(BaseModel):
    report_id: str
    issue_type: str
    latitude: float
    longitude: float
    severity: str
    status: str
    validation_status: str
    timestamp: dt.datetime


class ValidationRequest(BaseModel):
    validation_status: str
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("validation_status")
    @classmethod
    def _validation(cls, value: str) -> str:
        matched = title_match(value, VALIDATION_STATUSES)
        if not matched:
            raise ValueError(f"validation_status must be one of {', '.join(VALIDATION_STATUSES)}")
        return matched


class StatusUpdateRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def _status(cls, value: str) -> str:
        matched = title_match(value, REPORT_STATUSES)
        if not matched:
            raise ValueError(f"status must be one of {', '.join(REPORT_STATUSES)}")
        return matched


class PriorityPrediction(BaseModel):
    report_id: str
    predicted_priority: str
    confidence: float
    model: str
    rationale: list[str] = []
    probabilities: dict[str, float] = {}


class PriorityConfirmRequest(BaseModel):
    final_priority: str

    @field_validator("final_priority")
    @classmethod
    def _priority(cls, value: str) -> str:
        matched = title_match(value, PRIORITIES)
        if not matched:
            raise ValueError(f"final_priority must be one of {', '.join(PRIORITIES)}")
        return matched


class CsvRowError(BaseModel):
    row: int
    reportId: str | None = None
    reason: str


class CsvImportResult(BaseModel):
    totalRows: int
    successfulRows: int
    failedRows: int
    errors: list[CsvRowError] = []
    inserted: list[str] = []


class ImageAccess(BaseModel):
    """Temporary access to an evidence image."""

    url: str
    expires_in: int
    storage: str
    external: bool = False


class ReportFilters(BaseModel):
    issue_type: str | None = None
    severity: str | None = None
    validation_status: str | None = None
    status: str | None = None
    source: str | None = None
    priority: str | None = None
    date_from: dt.date | None = None
    date_to: dt.date | None = None
    location: str | None = None
    search: str | None = None


class AuditMetadata(BaseModel):
    data: dict[str, Any] = {}
