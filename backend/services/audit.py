"""Audit trail for authority and maintenance actions."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.entities import AuditLog
from backend.utils.datetimes import utcnow


def record(
    db: Session,
    *,
    user_id: str | None,
    role: str | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Append an audit entry.  The caller owns the transaction."""
    entry = AuditLog(
        user_id=user_id,
        role=role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        timestamp=utcnow(),
        audit_metadata=json.dumps(metadata, default=str) if metadata else None,
    )
    db.add(entry)
    return entry


def recent(db: Session, limit: int = 50, entity_id: str | None = None) -> list[dict[str, Any]]:
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
    if entity_id:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    rows = db.execute(stmt.limit(limit)).scalars().all()
    result = []
    for row in rows:
        meta = None
        if row.audit_metadata:
            try:
                meta = json.loads(row.audit_metadata)
            except json.JSONDecodeError:
                meta = {"raw": row.audit_metadata}
        result.append(
            {
                "id": row.id,
                "user_id": row.user_id,
                "role": row.role,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "timestamp": row.timestamp,
                "metadata": meta,
            }
        )
    return result
