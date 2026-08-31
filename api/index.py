"""Vercel Python entrypoint.

Vercel discovers ``api/index.py`` and serves the module-level ASGI ``app``.
The routers, services and models live under ``backend/`` so the same
application object also runs under ``uvicorn api.index:app`` locally.
"""

from __future__ import annotations

import os
import sys

# Vercel executes the function with the repository root on disk but not
# necessarily on sys.path, so add it explicitly before importing the package.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.main import app  # noqa: E402

# Vercel's Python runtime looks for `app` (ASGI) or `handler`.
handler = app

__all__ = ["app", "handler"]
