"""Mapping from ORM rows to API response payloads."""

from __future__ import annotations

from typing import Any

from backend.models.entities import MaintenanceTask, Notification, Report
from backend.utils.datetimes import ensure_utc


def task_brief(task: MaintenanceTask | None) -> dict[str, Any] | None:
    if task is None:
        return None
    return {
        "task_id": task.task_id,
        "assigned_team": task.assigned_team,
        "status": task.status,
        "assigned_at": ensure_utc(task.assigned_at),
        "completed_at": ensure_utc(task.completed_at),
        "verified_at": ensure_utc(task.verified_at),
        "maintenance_notes": task.maintenance_notes,
        "has_resolution_image": bool(
            task.resolution_image_object_key or task.resolution_image_url
        ),
    }


def report_out(report: Report, *, reporter_name: str | None = None, task: MaintenanceTask | None = None) -> dict[str, Any]:
    return {
        "id": report.id,
        "report_id": report.report_id,
        "user_id": report.user_id,
        "issue_type": report.issue_type,
        "location_text": report.location_text,
        "latitude": report.latitude,
        "longitude": report.longitude,
        "description": report.description,
        "severity": report.severity,
        "image_url": report.image_url,
        "has_image": bool(report.image_object_key or report.image_url),
        "timestamp": ensure_utc(report.timestamp),
        "validation_status": report.validation_status,
        "validated_by": report.validated_by,
        "validated_at": ensure_utc(report.validated_at),
        "predicted_priority": report.predicted_priority,
        "prediction_confidence": report.prediction_confidence,
        "final_priority": report.final_priority,
        "priority_confirmed_by": report.priority_confirmed_by,
        "priority_confirmed_at": ensure_utc(report.priority_confirmed_at),
        "status": report.status,
        "source": report.source,
        "created_at": ensure_utc(report.created_at),
        "updated_at": ensure_utc(report.updated_at),
        "reporter_name": reporter_name,
        "task": task_brief(task),
    }


def report_brief(report: Report | None) -> dict[str, Any] | None:
    if report is None:
        return None
    return {
        "report_id": report.report_id,
        "issue_type": report.issue_type,
        "location_text": report.location_text,
        "latitude": report.latitude,
        "longitude": report.longitude,
        "description": report.description,
        "severity": report.severity,
        "status": report.status,
        "validation_status": report.validation_status,
        "final_priority": report.final_priority,
        "predicted_priority": report.predicted_priority,
        "timestamp": ensure_utc(report.timestamp),
        "image_url": report.image_url,
        "has_image": bool(report.image_object_key or report.image_url),
    }


def task_out(task: MaintenanceTask, report: Report | None = None) -> dict[str, Any]:
    return {
        "id": task.id,
        "task_id": task.task_id,
        "report_id": task.report_id,
        "assigned_team": task.assigned_team,
        "assigned_to": task.assigned_to,
        "assigned_by": task.assigned_by,
        "assigned_at": ensure_utc(task.assigned_at),
        "status": task.status,
        "maintenance_notes": task.maintenance_notes,
        "resolution_image_url": task.resolution_image_url,
        "has_resolution_image": bool(
            task.resolution_image_object_key or task.resolution_image_url
        ),
        "completed_at": ensure_utc(task.completed_at),
        "verified_by": task.verified_by,
        "verified_at": ensure_utc(task.verified_at),
        "verification_notes": task.verification_notes,
        "created_at": ensure_utc(task.created_at),
        "updated_at": ensure_utc(task.updated_at),
        "report": report_brief(report),
    }


def notification_out(notification: Notification) -> dict[str, Any]:
    return {
        "id": notification.id,
        "notification_id": notification.notification_id,
        "user_id": notification.user_id,
        "report_id": notification.report_id,
        "title": notification.title,
        "message": notification.message,
        "type": notification.type,
        "is_read": notification.is_read,
        "created_at": ensure_utc(notification.created_at),
    }
