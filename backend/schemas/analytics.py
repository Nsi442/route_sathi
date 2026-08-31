"""Analytics schemas for the authority dashboard."""

from __future__ import annotations

from pydantic import BaseModel

from backend.schemas.common import CountByKey


class DashboardOverview(BaseModel):
    total_reports: int = 0
    new_reports: int = 0
    under_review: int = 0
    valid_reports: int = 0
    invalid_reports: int = 0
    assigned_tasks: int = 0
    in_progress: int = 0
    resolved: int = 0
    high_severity_open: int = 0
    awaiting_verification: int = 0
    total_facilities: int = 0
    resolution_rate: float = 0.0


class TrendPoint(BaseModel):
    date: str
    submitted: int = 0
    resolved: int = 0


class AnalyticsResponse(BaseModel):
    by_issue_type: list[CountByKey] = []
    by_severity: list[CountByKey] = []
    by_status: list[CountByKey] = []
    by_validation: list[CountByKey] = []
    by_priority: list[CountByKey] = []
    by_source: list[CountByKey] = []
    by_location: list[CountByKey] = []
    trend: list[TrendPoint] = []
    average_resolution_hours: float | None = None
    total_reports: int = 0


class LatestUpdate(BaseModel):
    report_id: str
    issue_type: str
    location_text: str | None = None
    status: str
    severity: str
    timestamp: str


class UserHomeSummary(BaseModel):
    name: str
    ramps: int = 0
    entrances: int = 0
    toilets: int = 0
    parking: int = 0
    issues: int = 0
    my_reports: int = 0
    unread_notifications: int = 0
    radius: int = 1000
    latest_updates: list[LatestUpdate] = []
