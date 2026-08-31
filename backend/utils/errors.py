"""Turning validation failures into messages the UI can display."""

from __future__ import annotations

from typing import Any


def jsonable_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Strip non-serialisable objects (pydantic puts exceptions in ``ctx``)."""
    cleaned: list[dict[str, Any]] = []
    for error in errors:
        item = {
            "loc": [str(part) for part in error.get("loc", ())],
            "type": str(error.get("type", "value_error")),
            "msg": str(error.get("msg", "Invalid value")),
        }
        if "input" in error:
            try:
                item["input"] = str(error["input"])[:200]
            except Exception:  # pragma: no cover - defensive
                pass
        cleaned.append(item)
    return cleaned


def first_error_message(exc) -> str:
    """Human-readable message for the first failing field."""
    errors = exc.errors() if hasattr(exc, "errors") else []
    if not errors:
        return "The submitted data is not valid."
    first = errors[0]
    location = ".".join(
        str(part) for part in first.get("loc", ()) if part not in ("body", "query")
    )
    message = str(first.get("msg", "Invalid value")).replace("Value error, ", "")
    return f"{location}: {message}" if location else message
