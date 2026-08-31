"""Maintenance portal: assigned tasks, status updates, resolution upload."""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.core.constants import TASK_STATUSES, title_match
from backend.core.deps import (
    bearer_scheme,
    require_maintenance,
    require_staff,
    resolve_media_principal,
)
from backend.core.security import create_media_token
from backend.db.session import get_db
from backend.models.entities import MaintenanceTask, Report, User
from backend.core.config import settings
from backend.schemas.common import Page
from backend.schemas.reports import ImageAccess
from backend.schemas.maintenance import (
    MaintenanceSummary,
    TaskNotesUpdate,
    TaskOut,
    TaskStatusUpdate,
)
from backend.services import audit, notifications, storage
from backend.services.serializers import task_out
from backend.utils.datetimes import utcnow

router = APIRouter(prefix="/maintenance", tags=["maintenance"])


def _visible_tasks(current_user: User):
    """A maintenance user sees tasks assigned to them personally or to their team."""
    clauses = [MaintenanceTask.assigned_to == current_user.user_id]
    if current_user.team:
        clauses.append(
            (MaintenanceTask.assigned_team == current_user.team)
            & (MaintenanceTask.assigned_to.is_(None))
        )
    return or_(*clauses)


def _get_task(db: Session, task_id: str, current_user: User) -> MaintenanceTask:
    task = db.execute(
        select(MaintenanceTask).where(MaintenanceTask.task_id == task_id)
    ).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if current_user.role == "MAINTENANCE":
        owns = task.assigned_to == current_user.user_id
        team_task = (
            task.assigned_to is None
            and current_user.team is not None
            and task.assigned_team == current_user.team
        )
        if not (owns or team_task):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This task is not assigned to you or your team.",
            )
    return task


def _report_for(db: Session, task: MaintenanceTask) -> Report | None:
    return db.execute(
        select(Report).where(Report.report_id == task.report_id)
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
@router.get("/summary", response_model=MaintenanceSummary)
def summary(
    db: Session = Depends(get_db), current_user: User = Depends(require_maintenance)
):
    rows = db.execute(
        select(MaintenanceTask.status, func.count())
        .where(_visible_tasks(current_user))
        .group_by(MaintenanceTask.status)
    ).all()
    counts = {status_name: int(count) for status_name, count in rows}
    return {
        "assigned": counts.get("Assigned", 0),
        "in_progress": counts.get("In Progress", 0),
        "completed": counts.get("Completed", 0),
        "verified": counts.get("Verified", 0),
        "rejected": counts.get("Rejected", 0),
        "total": sum(counts.values()),
    }


@router.get("/tasks", response_model=Page[TaskOut])
def my_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_maintenance),
):
    stmt = select(MaintenanceTask).where(_visible_tasks(current_user))
    if status_filter:
        matched = title_match(status_filter, TASK_STATUSES)
        if not matched:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"status must be one of {', '.join(TASK_STATUSES)}",
            )
        stmt = stmt.where(MaintenanceTask.status == matched)
    if search:
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(MaintenanceTask.task_id).like(needle),
                func.lower(MaintenanceTask.report_id).like(needle),
            )
        )

    total = int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())
    rows = (
        db.execute(
            stmt.order_by(MaintenanceTask.assigned_at.desc(), MaintenanceTask.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return {
        "items": [task_out(task, _report_for(db, task)) for task in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/tasks/{task_id}", response_model=TaskOut)
def task_detail(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_maintenance),
):
    task = _get_task(db, task_id, current_user)
    return task_out(task, _report_for(db, task))


@router.post("/tasks/{task_id}/status", response_model=TaskOut)
def update_status(
    task_id: str,
    payload: TaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_maintenance),
):
    """Move a task between Assigned -> In Progress -> Completed.

    Verification is an authority action, so a maintenance user cannot set
    ``Verified`` or ``Rejected`` here.
    """
    if payload.status in ("Verified", "Rejected"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an authority reviewer can verify or reject a resolution.",
        )

    task = _get_task(db, task_id, current_user)
    if task.status == "Verified":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This task has already been verified and is closed.",
        )
    if payload.status == "Completed" and not (
        task.resolution_image_object_key or task.resolution_image_url
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload a resolution photo before submitting the task as completed.",
        )

    previous = task.status
    now = utcnow()
    task.status = payload.status
    if payload.maintenance_notes is not None:
        task.maintenance_notes = payload.maintenance_notes
    if task.assigned_to is None:
        # First responder from the team claims the task.
        task.assigned_to = current_user.user_id
    if payload.status == "Completed":
        task.completed_at = now
    task.updated_at = now

    report = _report_for(db, task)
    if report is not None:
        if payload.status == "In Progress":
            report.status = "In Progress"
            notifications.report_in_progress(db, report.user_id, report.report_id)
        elif payload.status == "Completed":
            # The citizen is told it is resolved only after authority verification.
            report.status = "In Progress"
        report.updated_at = now

    db.flush()
    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="task.status",
        entity_type="task",
        entity_id=task.task_id,
        metadata={"from": previous, "to": payload.status, "report_id": task.report_id},
    )
    db.commit()
    db.refresh(task)
    return task_out(task, report)


@router.patch("/tasks/{task_id}/notes", response_model=TaskOut)
def update_notes(
    task_id: str,
    payload: TaskNotesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_maintenance),
):
    task = _get_task(db, task_id, current_user)
    task.maintenance_notes = payload.maintenance_notes
    task.updated_at = utcnow()
    db.flush()
    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="task.notes",
        entity_type="task",
        entity_id=task.task_id,
    )
    db.commit()
    db.refresh(task)
    return task_out(task, _report_for(db, task))


@router.post("/tasks/{task_id}/resolution", response_model=TaskOut)
async def upload_resolution_image(
    task_id: str,
    photo: UploadFile = File(...),
    maintenance_notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_maintenance),
):
    """Upload the 'after' photo proving the issue was fixed.

    Stored in S3 as ``resolutions/<year>/<month>/<report id>-fixed.<ext>``; the
    database keeps only the object key.
    """
    task = _get_task(db, task_id, current_user)
    if task.status == "Verified":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This task has already been verified and is closed.",
        )

    data = await photo.read()
    extension = storage.extension_for(photo.content_type, photo.filename)
    try:
        object_key = storage.put_object(
            db,
            object_key=storage.unique_object_key(
                "resolutions", f"{task.report_id}-fixed", extension
            ),
            data=data,
            content_type=photo.content_type or "image/jpeg",
        )
    except storage.StorageError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    task.resolution_image_object_key = object_key
    if maintenance_notes:
        task.maintenance_notes = maintenance_notes
    if task.assigned_to is None:
        task.assigned_to = current_user.user_id
    if task.status == "Assigned":
        task.status = "In Progress"
    task.updated_at = utcnow()
    db.flush()
    audit.record(
        db,
        user_id=current_user.user_id,
        role=current_user.role,
        action="task.resolution_upload",
        entity_type="task",
        entity_id=task.task_id,
        metadata={"object_key": object_key, "report_id": task.report_id},
    )
    db.commit()
    db.refresh(task)
    return task_out(task, _report_for(db, task))


@router.get("/tasks/{task_id}/resolution/link", response_model=ImageAccess)
def resolution_image_link(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Return a short-lived link to the resolution photo.

    With S3 configured this is a presigned URL; otherwise it is a URL carrying
    a scoped media token, because a browser cannot attach the bearer header to
    an image or download link.
    """
    task = _get_task(db, task_id, current_user)
    if not task.resolution_image_object_key:
        if task.resolution_image_url:
            return {
                "url": task.resolution_image_url,
                "expires_in": 0,
                "storage": "external-url",
                "external": True,
            }
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resolution image has been uploaded for this task.",
        )

    url = storage.presigned_url(task.resolution_image_object_key)
    if url:
        return {
            "url": url,
            "expires_in": settings.s3_presign_expiry,
            "storage": "s3",
            "external": False,
        }

    token, expires_in = create_media_token(
        subject=current_user.user_id,
        role=current_user.role,
        resource=f"task:{task_id}",
    )
    return {
        "url": f"/api/maintenance/tasks/{task_id}/resolution?token={token}",
        "expires_in": expires_in,
        "storage": storage.backend_name(),
        "external": False,
    }


@router.get("/tasks/{task_id}/resolution")
def resolution_image(
    task_id: str,
    token: str | None = Query(default=None, description="Short-lived media token"),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    """Serve the resolution photo to the maintenance owner or an authority reviewer."""
    current_user = resolve_media_principal(
        db,
        resource=f"task:{task_id}",
        credentials=credentials,
        token=token,
    )
    if current_user.role not in ("MAINTENANCE", "AUTHORITY"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this image.",
        )
    task = _get_task(db, task_id, current_user)
    if not task.resolution_image_object_key:
        if task.resolution_image_url:
            return RedirectResponse(task.resolution_image_url, status_code=307)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No resolution image has been uploaded for this task.",
        )

    url = storage.presigned_url(task.resolution_image_object_key)
    if url:
        return RedirectResponse(url, status_code=307)

    blob = storage.fetch_fallback(db, task.resolution_image_object_key)
    if blob is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image data is unavailable."
        )
    data, content_type = blob
    return Response(
        content=data,
        media_type=content_type,
        headers={"Cache-Control": "private, max-age=300"},
    )
