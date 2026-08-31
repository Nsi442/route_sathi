"""Accessibility facility schemas."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, Field, field_validator

from backend.core.constants import FACILITY_STATUSES, FACILITY_TYPES, title_match
from backend.schemas.common import ORMModel


class FacilityBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    type: str
    description: str | None = None
    address: str | None = Field(default=None, max_length=300)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    status: str = "Available"
    source: str | None = None

    @field_validator("type")
    @classmethod
    def _type(cls, value: str) -> str:
        matched = title_match(value, FACILITY_TYPES)
        if not matched:
            raise ValueError(f"type must be one of {', '.join(FACILITY_TYPES)}")
        return matched

    @field_validator("status")
    @classmethod
    def _status(cls, value: str) -> str:
        matched = title_match(value, FACILITY_STATUSES)
        if not matched:
            raise ValueError(f"status must be one of {', '.join(FACILITY_STATUSES)}")
        return matched


class FacilityCreate(FacilityBase):
    pass


class FacilityUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    address: str | None = None
    status: str | None = None

    @field_validator("status")
    @classmethod
    def _status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        matched = title_match(value, FACILITY_STATUSES)
        if not matched:
            raise ValueError(f"status must be one of {', '.join(FACILITY_STATUSES)}")
        return matched


class FacilityOut(ORMModel):
    id: int
    facility_id: str
    name: str
    type: str
    description: str | None = None
    address: str | None = None
    latitude: float
    longitude: float
    status: str
    source: str | None = None
    last_updated: dt.datetime | None = None
    created_at: dt.datetime


class FacilityNearby(BaseModel):
    facility_id: str
    name: str
    type: str
    description: str | None = None
    address: str | None = None
    latitude: float
    longitude: float
    status: str
    source: str | None = None
    last_updated: dt.datetime | None = None
    distance: float = Field(..., description="Straight-line distance in metres")


class FacilitySummary(BaseModel):
    """Counts used by the user home screen ('Accessibility Around You')."""

    ramps: int = 0
    entrances: int = 0
    toilets: int = 0
    parking: int = 0
    crossings: int = 0
    pathways: int = 0
    issues: int = 0
    radius: int = 1000
