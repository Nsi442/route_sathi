"""Object storage for report evidence and resolution images.

Primary backend: **Amazon S3**.  Binary images never enter PostgreSQL - the
database holds only the object key, and reads are served through short-lived
presigned URLs so the bucket can stay private.

    User -> React -> FastAPI -> S3 -> object key -> PostgreSQL

When S3 credentials are not configured (local development, CI, a reviewer
cloning the repo) the service transparently falls back to the ``stored_files``
table so the whole upload/serve flow still works end to end.  The fallback is
never used when ``S3_BUCKET`` and the AWS credentials are present.
"""

from __future__ import annotations

import base64
import datetime as dt
import logging
import mimetypes
import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.models.entities import StoredFile
from backend.utils.datetimes import utcnow

logger = logging.getLogger("routesathi.storage")

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}

_SAFE_KEY = re.compile(r"^[A-Za-z0-9._/-]{1,400}$")

_s3_client = None


class StorageError(RuntimeError):
    """Raised when an upload cannot be completed."""


def _client():
    """Lazily build the boto3 S3 client (module-level cached per container)."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    if not settings.s3_enabled:
        return None
    try:
        import boto3
        from botocore.config import Config

        _s3_client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )
        return _s3_client
    except Exception as exc:  # pragma: no cover - depends on AWS availability
        logger.warning("S3 client unavailable (%s); falling back to database storage", exc)
        return None


def backend_name() -> str:
    return "s3" if _client() is not None else "database-fallback"


def extension_for(content_type: str | None, filename: str | None) -> str:
    if content_type and content_type.lower() in ALLOWED_CONTENT_TYPES:
        return ALLOWED_CONTENT_TYPES[content_type.lower()]
    if filename and "." in filename:
        suffix = "." + filename.rsplit(".", 1)[-1].lower()
        if suffix in ALLOWED_CONTENT_TYPES.values():
            return suffix
    guessed = mimetypes.guess_extension(content_type or "") or ".jpg"
    return guessed


def build_object_key(prefix: str, identifier: str, extension: str, when: dt.datetime | None = None) -> str:
    """``reports/2026/08/RS-1001.jpg`` / ``resolutions/2026/08/RS-1001-fixed.jpg``."""
    when = when or utcnow()
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "-", identifier)
    return f"{prefix}/{when:%Y}/{when:%m}/{safe_id}{extension}"


def unique_object_key(prefix: str, identifier: str, extension: str) -> str:
    """Object key with a short random component to avoid overwriting history."""
    base = build_object_key(prefix, identifier, "")
    return f"{base}-{uuid.uuid4().hex[:8]}{extension}"


def validate_upload(content_type: str | None, size: int) -> None:
    if content_type and content_type.lower() not in ALLOWED_CONTENT_TYPES:
        raise StorageError(
            "Unsupported image type. Upload a JPEG, PNG, WEBP or HEIC image."
        )
    if size <= 0:
        raise StorageError("The uploaded file is empty.")
    if size > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes // (1024 * 1024)
        raise StorageError(f"Image is larger than the {limit_mb} MB limit.")


def put_object(
    db: Session,
    *,
    object_key: str,
    data: bytes,
    content_type: str,
) -> str:
    """Store bytes and return the object key that was written."""
    validate_upload(content_type, len(data))

    client = _client()
    if client is not None:
        try:
            client.put_object(
                Bucket=settings.s3_bucket,
                Key=object_key,
                Body=data,
                ContentType=content_type,
                # Objects stay private; access is granted via presigned URLs.
                ACL="private",
                ServerSideEncryption="AES256",
            )
            return object_key
        except Exception as exc:  # pragma: no cover - network dependent
            logger.error("S3 upload failed for %s: %s", object_key, exc)
            raise StorageError("Could not store the image. Please retry.") from exc

    existing = db.execute(
        select(StoredFile).where(StoredFile.object_key == object_key)
    ).scalar_one_or_none()
    encoded = base64.b64encode(data).decode("ascii")
    if existing:
        existing.content_type = content_type
        existing.size_bytes = len(data)
        existing.data_base64 = encoded
    else:
        db.add(
            StoredFile(
                object_key=object_key,
                content_type=content_type,
                size_bytes=len(data),
                data_base64=encoded,
                created_at=utcnow(),
            )
        )
    db.flush()
    return object_key


def presigned_url(object_key: str, expires_in: int | None = None) -> str | None:
    """Short-lived GET url for a private S3 object."""
    client = _client()
    if client is None:
        return None
    expiry = expires_in or settings.s3_presign_expiry
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": object_key},
            ExpiresIn=expiry,
        )
    except Exception as exc:  # pragma: no cover
        logger.error("Could not presign %s: %s", object_key, exc)
        return None


def fetch_fallback(db: Session, object_key: str) -> tuple[bytes, str] | None:
    """Read an object back from the development fallback store."""
    record = db.execute(
        select(StoredFile).where(StoredFile.object_key == object_key)
    ).scalar_one_or_none()
    if record is None:
        return None
    return base64.b64decode(record.data_base64), record.content_type


def delete_object(db: Session, object_key: str) -> None:
    client = _client()
    if client is not None:
        try:
            client.delete_object(Bucket=settings.s3_bucket, Key=object_key)
        except Exception as exc:  # pragma: no cover
            logger.warning("Could not delete %s from S3: %s", object_key, exc)
        return
    record = db.execute(
        select(StoredFile).where(StoredFile.object_key == object_key)
    ).scalar_one_or_none()
    if record is not None:
        db.delete(record)


def is_safe_key(object_key: str) -> bool:
    return bool(_SAFE_KEY.match(object_key)) and ".." not in object_key
