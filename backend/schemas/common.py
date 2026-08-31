"""Shared Pydantic schemas."""

from __future__ import annotations

import datetime as dt
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    detail: str


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20
    pages: int = 1


class Coordinates(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: float | None = None
    timestamp: dt.datetime | None = None


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
    database: str
    spatial_backend: str
    object_storage: str
    ml_backend: str
    time: dt.datetime


class CountByKey(BaseModel):
    key: str
    count: int


class AuditEntry(BaseModel):
    id: int
    user_id: str | None = None
    role: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    timestamp: dt.datetime
    metadata: dict[str, Any] | None = None
