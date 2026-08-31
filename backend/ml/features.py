"""Feature engineering for the priority model.

The feature vector is deliberately small and fully derivable from a report row
so that the same code path serves training, batch scoring and single-report
inference.
"""

from __future__ import annotations

import datetime as dt

from backend.core.constants import ISSUE_TYPES, SEVERITY_ORDER

# Impact weight of each issue type on pedestrian/wheelchair accessibility.
ISSUE_IMPACT = {
    "Ramp Blocked": 0.90,
    "No Accessible Entrance": 0.85,
    "Stairs / No Ramp": 0.80,
    "Blocked Crossing": 0.75,
    "Waterlogging": 0.70,
    "Footpath Damaged": 0.55,
    "Other": 0.35,
}

SOURCE_TRUST = {
    "Municipal": 0.9,
    "Field Survey": 0.85,
    "Partner": 0.7,
    "Citizen App": 0.6,
    "Community": 0.55,
    "Other": 0.4,
}

FEATURE_NAMES = [
    "severity_ordinal",
    "issue_impact",
    "source_trust",
    "has_image",
    "description_length",
    "description_words",
    "age_days",
    "hour_of_day",
    "is_weekend",
    "is_validated",
    *[f"issue_{i}" for i in range(len(ISSUE_TYPES))],
]


def _age_days(timestamp: dt.datetime | None, now: dt.datetime | None = None) -> float:
    if timestamp is None:
        return 0.0
    now = now or dt.datetime.now(dt.timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=dt.timezone.utc)
    return max(0.0, (now - timestamp).total_seconds() / 86400.0)


def extract(
    *,
    issue_type: str,
    severity: str,
    source: str | None,
    description: str | None,
    has_image: bool,
    timestamp: dt.datetime | None,
    validation_status: str | None = None,
    now: dt.datetime | None = None,
) -> list[float]:
    """Return the ordered numeric feature vector for one report."""
    description = description or ""
    issue_type = issue_type if issue_type in ISSUE_IMPACT else "Other"
    local_hour = 12
    is_weekend = 0.0
    if timestamp is not None:
        local = timestamp + dt.timedelta(hours=5, minutes=30)  # IST
        local_hour = local.hour
        is_weekend = 1.0 if local.weekday() >= 5 else 0.0

    one_hot = [1.0 if issue_type == name else 0.0 for name in ISSUE_TYPES]

    return [
        float(SEVERITY_ORDER.get(severity, 0)),
        ISSUE_IMPACT.get(issue_type, 0.35),
        SOURCE_TRUST.get(source or "Other", 0.4),
        1.0 if has_image else 0.0,
        float(min(len(description), 600)),
        float(min(len(description.split()), 120)),
        _age_days(timestamp, now),
        float(local_hour),
        is_weekend,
        1.0 if validation_status == "Valid" else 0.0,
        *one_hot,
    ]


def explain(
    *,
    issue_type: str,
    severity: str,
    source: str | None,
    has_image: bool,
    timestamp: dt.datetime | None,
    validation_status: str | None = None,
) -> list[str]:
    """Short, human-readable reasons shown next to the recommendation."""
    reasons: list[str] = []
    impact = ISSUE_IMPACT.get(issue_type, 0.35)
    if impact >= 0.8:
        reasons.append(f"'{issue_type}' fully blocks step-free access")
    elif impact >= 0.6:
        reasons.append(f"'{issue_type}' significantly restricts step-free access")
    else:
        reasons.append(f"'{issue_type}' has a moderate accessibility impact")

    reasons.append(f"Citizen-reported severity is {severity}")

    age = _age_days(timestamp)
    if age >= 14:
        reasons.append(f"Report has been open for {int(age)} days")
    elif age >= 7:
        reasons.append(f"Report is {int(age)} days old")

    reasons.append(
        "Photo evidence attached" if has_image else "No photo evidence attached"
    )
    if validation_status == "Valid":
        reasons.append("Already validated by an authority reviewer")
    if source:
        reasons.append(f"Source: {source}")
    return reasons
