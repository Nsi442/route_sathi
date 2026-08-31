"""FastAPI application factory.

A single ``app`` object is exported and mounted by ``api/index.py``, which is
the Vercel Python entrypoint.  Everything the API needs is request-scoped:
there are no background workers, no local filesystem writes outside ``/tmp``
and no long-lived connections, so the same app runs unchanged under Uvicorn
locally and as a Vercel serverless function.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.core.config import settings
from backend.db.geo import spatial_backend
from backend.db.init_db import init_db
from backend.db.session import engine
from backend.ml import priority as ml_priority
from backend.routers import (
    analytics,
    authority,
    auth,
    facilities,
    maintenance,
    notifications,
    reports,
    users,
)
from backend.schemas.common import HealthResponse
from backend.services import storage
from backend.utils.datetimes import utcnow
from backend.utils.errors import first_error_message, jsonable_errors

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("routesathi")

DESCRIPTION = """
**RouteSathi** - *Accessible Places. Better Access.*

Location-based accessibility discovery, issue reporting, authority management
and maintenance tracking.

Three role-based portals share this API:

| Portal | Role | Prefix |
| --- | --- | --- |
| Citizen app | `USER` | `/api/user`, `/api/facilities`, `/api/notifications` |
| Authority dashboard | `AUTHORITY` | `/api/authority`, `/api/analytics` |
| Maintenance portal | `MAINTENANCE` | `/api/maintenance` |

Authenticate with `POST /api/auth/login` and send the returned JWT as
`Authorization: Bearer <token>`.

The map is used for discovery and visualisation only - this MVP deliberately
contains no routing engine, navigation or route optimisation.
"""


def create_app() -> FastAPI:
    app = FastAPI(
        title="RouteSathi API",
        description=DESCRIPTION,
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # The database bootstrap is idempotent and guarded by a module flag, so
    # warm containers skip it.  Startup events do not fire reliably on every
    # serverless platform, hence the explicit call here.
    try:
        init_db()
    except Exception as exc:  # pragma: no cover - surfaced through /api/health
        logger.error("Database initialisation failed: %s", exc)

    for router in (
        auth.router,
        users.router,
        facilities.router,
        reports.router,
        authority.router,
        maintenance.router,
        notifications.router,
        analytics.router,
    ):
        app.include_router(router, prefix=settings.api_prefix)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        """Return the first field error as a readable message for the UI."""
        errors = jsonable_errors(exc.errors())
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": first_error_message(exc), "errors": errors[:10]},
        )

    @app.get(f"{settings.api_prefix}/health", response_model=HealthResponse, tags=["system"])
    def health():
        """Liveness probe reporting which backends are actually in use."""
        database = "unavailable"
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            database = "postgresql" if settings.is_postgres else "sqlite"
        except Exception as exc:  # pragma: no cover
            logger.error("Health check database error: %s", exc)

        return {
            "status": "ok" if database != "unavailable" else "degraded",
            "app": settings.app_name,
            "environment": settings.app_env,
            "database": database,
            "spatial_backend": spatial_backend(),
            "object_storage": storage.backend_name(),
            "ml_backend": ml_priority.backend_name() if settings.ml_enabled else "disabled",
            "time": utcnow(),
        }

    @app.get(f"{settings.api_prefix}", tags=["system"])
    def api_root():
        return {
            "name": "RouteSathi API",
            "tagline": "Accessible Places. Better Access.",
            "version": "1.0.0",
            "docs": f"{settings.api_prefix}/docs",
            "portals": ["USER", "AUTHORITY", "MAINTENANCE"],
        }

    return app


app = create_app()
