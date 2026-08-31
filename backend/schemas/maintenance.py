"""Maintenance task schemas."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, field_validator

from backend.core.constants import TASK_STATUSES, title_match
from backend.schemas.common import ORMModel


class AssignRequest(BaseModel):
    assigned_team: str = Field(..., min_length=2, max_length=120)
    assigned_to: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=1000)


class TaskStatusUpdate(BaseModel):
    status: str
    maintenance_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("status")
    @classmethod
    def _status(cls, value: str) -> str:
        matched = title_match(value, TASK_STATUSES)
        if not matched:
            raise ValueError(f"status must be one of {', '.join(TASK_STATUSES)}")
        return matched


class TaskNotesUpdate(BaseModel):
    maintenance_notes: str = Field(..., max_length=2000)


class VerifyRequest(BaseModel):
    approved: bool
    notes: str | None = Field(default=None, max_length=1000)


class ReportBrief(BaseModel):
    report_id: str
    issue_type: str
    location_text: str | None = None
    latitude: float
    longitude: float
    description: str | None = None
    severity: str
    status: str
    validation_status: str
    final_priority: str | None = None
    predicted_priority: str | None = None
    timestamp: dt.datetime
    image_url: str | None = None
    has_image: bool = False


class TaskOut(ORMModel):
    id: int
    task_id: str
    report_id: str
    assigned_team: str
    assigned_to: str | None = None
    assigned_by: str | None = None
    assigned_at: dt.datetime | None = None
    status: str
    maintenance_notes: str | None = None
    resolution_image_url: str | None = None
    has_resolution_image: bool = False
    completed_at: dt.datetime | None = None
    verified_by: str | None = None
    verified_at: dt.datetime | None = None
    verification_notes: str | None = None
    created_at: dt.datetime
    updated_at: dt.datetime
    report: ReportBrief | None = None


class MaintenanceSummary(BaseModel):
    assigned: int = 0
    in_progress: int = 0
    completed: int = 0
    verified: int = 0
    rejected: int = 0
    total: int = 0
