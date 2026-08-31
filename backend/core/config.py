"""Central application configuration.

Every value is read from the environment so that no secret ever lives in the
repository.  ``.env.example`` documents the full set of variables.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


def _load_dotenv() -> None:
    """Minimal .env loader (no external dependency).

    Vercel injects environment variables directly, so this only matters for
    local development.  Existing environment variables always win.
    """
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parents[2] / ".env"):
        if not candidate.is_file():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
        break


_load_dotenv()


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except (TypeError, ValueError):
        return default


class Settings:
    """Runtime settings resolved once per cold start."""

    def __init__(self) -> None:
        self.app_name: str = "RouteSathi API"
        self.app_env: str = os.getenv("APP_ENV", "development")
        self.api_prefix: str = "/api"

        # --- database ---------------------------------------------------
        self.database_url: str = self._normalise_db_url(
            os.getenv("DATABASE_URL", "").strip()
        )

        # --- auth -------------------------------------------------------
        self.jwt_secret: str = os.getenv("JWT_SECRET", "").strip() or (
            "routesathi-insecure-development-secret-change-me"
        )
        self.jwt_algorithm: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.access_token_expire_minutes: int = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 720)

        # --- object storage ---------------------------------------------
        self.aws_region: str = os.getenv("AWS_REGION", "ap-south-1")
        self.s3_bucket: str = os.getenv("S3_BUCKET", "").strip()
        self.s3_presign_expiry: int = _int("S3_PRESIGN_EXPIRY", 900)
        self.aws_access_key_id: str = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
        self.aws_secret_access_key: str = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()

        # --- machine learning -------------------------------------------
        self.ml_enabled: bool = _bool("ML_ENABLED", True)
        self.ml_model_dir: str = os.getenv("ML_MODEL_DIR", "/tmp/routesathi-ml")

        # --- misc --------------------------------------------------------
        self.cors_origins: list[str] = [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        ]
        self.seed_default_password: str = os.getenv("SEED_DEFAULT_PASSWORD", "Password123!")
        self.max_upload_bytes: int = _int("MAX_UPLOAD_BYTES", 8 * 1024 * 1024)

    # ------------------------------------------------------------------
    @staticmethod
    def _normalise_db_url(url: str) -> str:
        """Return a SQLAlchemy-compatible URL.

        Neon hands out ``postgresql://`` (or ``postgres://``) URLs; SQLAlchemy
        needs an explicit driver so that psycopg 3 is used rather than the
        unavailable psycopg2.  When nothing is configured we fall back to a
        local SQLite file so the MVP runs with zero setup.
        """
        if not url:
            return "sqlite:///./routesathi.db"
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url

    # ------------------------------------------------------------------
    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def s3_enabled(self) -> bool:
        """True when a real S3 bucket is reachable with the configured creds."""
        return bool(self.s3_bucket and self.aws_access_key_id and self.aws_secret_access_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
