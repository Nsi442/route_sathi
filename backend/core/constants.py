"""Domain enumerations shared by the API, the CSV importer and the frontend."""

from __future__ import annotations

# --- roles ------------------------------------------------------------------
ROLE_USER = "USER"
ROLE_AUTHORITY = "AUTHORITY"
ROLE_MAINTENANCE = "MAINTENANCE"
ROLES = (ROLE_USER, ROLE_AUTHORITY, ROLE_MAINTENANCE)

# --- accessibility facilities ----------------------------------------------
FACILITY_TYPES = (
    "Ramp",
    "Entrance",
    "Toilet",
    "Parking",
    "Crossing",
    "Pathway",
    "Other",
)
FACILITY_STATUSES = ("Verified", "Available", "Under Review", "Blocked", "Inactive")

# --- reports ----------------------------------------------------------------
ISSUE_TYPES = (
    "Ramp Blocked",
    "Footpath Damaged",
    "No Accessible Entrance",
    "Stairs / No Ramp",
    "Waterlogging",
    "Blocked Crossing",
    "Other",
)

# Values that appear in third-party/bulk CSV exports mapped onto our canonical
# issue types.  Keys are compared case-insensitively after whitespace squashing.
ISSUE_TYPE_ALIASES = {
    "blocked ramp": "Ramp Blocked",
    "ramp blocked": "Ramp Blocked",
    "ramp obstruction": "Ramp Blocked",
    "damaged footpath": "Footpath Damaged",
    "footpath damaged": "Footpath Damaged",
    "broken footpath": "Footpath Damaged",
    "damaged pathway": "Footpath Damaged",
    "no accessible entrance": "No Accessible Entrance",
    "inaccessible entrance": "No Accessible Entrance",
    "no ramp": "Stairs / No Ramp",
    "stairs / no ramp": "Stairs / No Ramp",
    "stairs no ramp": "Stairs / No Ramp",
    "stairs only": "Stairs / No Ramp",
    "waterlogging": "Waterlogging",
    "water logging": "Waterlogging",
    "flooding": "Waterlogging",
    "blocked crossing": "Blocked Crossing",
    "crossing blocked": "Blocked Crossing",
    "other": "Other",
}

SEVERITIES = ("Low", "Medium", "High")
SEVERITY_ORDER = {"Low": 0, "Medium": 1, "High": 2}

VALIDATION_STATUSES = ("Needs Review", "Valid", "Invalid")

REPORT_STATUSES = ("Submitted", "Under Review", "Assigned", "In Progress", "Resolved")

PRIORITIES = ("Low", "Medium", "High", "Critical")
PRIORITY_ORDER = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}

REPORT_SOURCES = ("Community", "Citizen App", "Field Survey", "Municipal", "Partner", "Other")

# --- maintenance ------------------------------------------------------------
TASK_STATUSES = ("Assigned", "In Progress", "Completed", "Verified", "Rejected")

MAINTENANCE_TEAMS = (
    "Team Alpha",
    "Team Bravo",
    "Team Charlie",
    "Drainage Unit",
    "Roads Unit",
)

# --- notifications ----------------------------------------------------------
NOTIFICATION_TYPES = (
    "report_submitted",
    "report_validated",
    "report_assigned",
    "report_in_progress",
    "report_resolved",
    "task_assigned",
    "task_verified",
    "task_rejected",
    "system",
)


def normalise_issue_type(value: str | None) -> str | None:
    """Map a free-text issue type onto a canonical issue type, if possible."""
    if not value:
        return None
    cleaned = " ".join(str(value).split())
    for canonical in ISSUE_TYPES:
        if cleaned.lower() == canonical.lower():
            return canonical
    return ISSUE_TYPE_ALIASES.get(cleaned.lower())


def title_match(value: str | None, allowed: tuple[str, ...]) -> str | None:
    """Case-insensitive lookup of ``value`` inside ``allowed``."""
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    for item in allowed:
        if cleaned.lower() == item.lower():
            return item
    return None
