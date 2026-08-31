"""End-to-end API tests covering the full report lifecycle.

Run with:  pytest -q
"""

from __future__ import annotations

import io
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point the app at a throwaway database before it is imported.
_TMP_DB = os.path.join(tempfile.mkdtemp(prefix="routesathi-test-"), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP_DB}"
os.environ["JWT_SECRET"] = "test-secret-not-used-in-production"
os.environ["ML_MODEL_DIR"] = tempfile.mkdtemp(prefix="routesathi-ml-")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from backend.core.security import hash_password  # noqa: E402
from backend.db.init_db import init_db  # noqa: E402
from backend.db.session import SessionLocal  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models.entities import (  # noqa: E402
    AccessibilityFacility,
    Notification,
    User,
)
from backend.utils.datetimes import utcnow  # noqa: E402

# A 1x1 PNG, small enough to keep the tests fast.
PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000100ffff03000006000557bfabd4"
    "0000000049454e44ae426082"
)

CSV_HEADER = (
    "report_id,user_id,issue_type,location,latitude,longitude,severity,"
    "description,image_url,timestamp,validation_status,status,source\n"
)


@pytest.fixture(scope="session", autouse=True)
def _database():
    init_db(force=True)
    with SessionLocal() as db:
        password = hash_password("Password123!")
        db.add_all(
            [
                User(
                    user_id="U1001",
                    name="Ananya Sen",
                    email="citizen@test.app",
                    password_hash=password,
                    role="USER",
                ),
                User(
                    user_id="AU101",
                    name="KMC Authority",
                    email="authority@test.app",
                    password_hash=password,
                    role="AUTHORITY",
                ),
                User(
                    user_id="MN201",
                    name="Team Alpha",
                    email="maintenance@test.app",
                    password_hash=password,
                    role="MAINTENANCE",
                    team="Team Alpha",
                ),
                AccessibilityFacility(
                    facility_id="FAC-1",
                    name="College Street Ramp",
                    type="Ramp",
                    latitude=22.5745,
                    longitude=88.3639,
                    status="Verified",
                    last_updated=utcnow(),
                ),
                AccessibilityFacility(
                    facility_id="FAC-2",
                    name="Salt Lake Ramp",
                    type="Ramp",
                    latitude=22.5726,
                    longitude=88.4331,
                    status="Available",
                    last_updated=utcnow(),
                ),
                AccessibilityFacility(
                    facility_id="FAC-3",
                    name="Park Street Toilet",
                    type="Toilet",
                    latitude=22.5533,
                    longitude=88.3521,
                    status="Available",
                    last_updated=utcnow(),
                ),
            ]
        )
        db.commit()
    yield


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _login(client, email: str, role: str | None = None) -> str:
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "Password123!", "role": role},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# System
# ---------------------------------------------------------------------------
def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["spatial_backend"] in ("postgis", "haversine")


# ---------------------------------------------------------------------------
# Authentication and authorisation
# ---------------------------------------------------------------------------
def test_signup_creates_citizen_and_returns_token(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "New Citizen",
            "email": "new.citizen@test.app",
            "phone": "+91 98300 55555",
            "password": "Password123!",
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "USER"
    assert body["user"]["user_id"].startswith("U")


def test_signup_rejects_duplicate_email(client):
    response = client.post(
        "/api/auth/signup",
        json={"name": "Copy", "email": "citizen@test.app", "password": "Password123!"},
    )
    assert response.status_code == 409


def test_signup_cannot_self_provision_authority(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "Fake Authority",
            "email": "fake.authority@test.app",
            "password": "Password123!",
            "role": "AUTHORITY",
        },
    )
    assert response.status_code == 403


def test_login_with_wrong_password_fails(client):
    response = client.post(
        "/api/auth/login", json={"email": "citizen@test.app", "password": "wrong"}
    )
    assert response.status_code == 401


def test_login_rejects_wrong_portal(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "citizen@test.app", "password": "Password123!", "role": "AUTHORITY"},
    )
    assert response.status_code == 403


def test_protected_endpoint_requires_token(client):
    assert client.get("/api/authority/overview").status_code == 401


def test_citizen_cannot_reach_authority_endpoints(client):
    token = _login(client, "citizen@test.app")
    assert client.get("/api/authority/overview", headers=_auth(token)).status_code == 403


def test_maintenance_cannot_reach_authority_endpoints(client):
    token = _login(client, "maintenance@test.app")
    assert client.get("/api/authority/reports", headers=_auth(token)).status_code == 403


# ---------------------------------------------------------------------------
# Facilities: PostGIS / haversine radius search
# ---------------------------------------------------------------------------
def test_nearby_search_filters_by_radius_and_type(client):
    token = _login(client, "citizen@test.app")
    response = client.get(
        "/api/facilities/nearby",
        params={
            "latitude": 22.5726,
            "longitude": 88.3639,
            "radius": 300,
            "type": "Ramp",
        },
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    items = response.json()
    # FAC-1 is ~210 m away; FAC-2 is ~7 km away and must be excluded.
    assert [item["facility_id"] for item in items] == ["FAC-1"]
    assert 0 < items[0]["distance"] <= 300


def test_nearby_search_orders_nearest_first(client):
    token = _login(client, "citizen@test.app")
    items = client.get(
        "/api/facilities/nearby",
        params={"latitude": 22.5726, "longitude": 88.3639, "radius": 20000},
        headers=_auth(token),
    ).json()
    distances = [item["distance"] for item in items]
    assert distances == sorted(distances)
    assert len(items) >= 3


def test_nearby_search_rejects_unknown_type(client):
    token = _login(client, "citizen@test.app")
    response = client.get(
        "/api/facilities/nearby",
        params={"latitude": 22.5, "longitude": 88.3, "radius": 500, "type": "Escalator"},
        headers=_auth(token),
    )
    assert response.status_code == 400


def test_facility_details(client):
    token = _login(client, "citizen@test.app")
    body = client.get("/api/facilities/FAC-1", headers=_auth(token)).json()
    assert body["name"] == "College Street Ramp"
    assert body["status"] == "Verified"


# ---------------------------------------------------------------------------
# Citizen reporting with photo evidence
# ---------------------------------------------------------------------------
def test_citizen_submits_report_with_photo(client):
    token = _login(client, "citizen@test.app")
    response = client.post(
        "/api/user/reports",
        data={
            "issue_type": "Ramp Blocked",
            "latitude": "22.5726",
            "longitude": "88.3639",
            "severity": "High",
            "description": "Ramp blocked by a parked car outside the college gate.",
            "location_text": "College Street, Kolkata",
        },
        files={"photo": ("evidence.png", io.BytesIO(PNG_BYTES), "image/png")},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["report_id"].startswith("RS-")
    assert body["validation_status"] == "Needs Review"
    assert body["status"] == "Submitted"
    assert body["source"] == "Citizen App"
    assert body["has_image"] is True
    assert body["timestamp"]

    # The evidence image is retrievable by its owner.
    link = client.get(
        f"/api/reports/{body['report_id']}/image", headers=_auth(token)
    )
    assert link.status_code == 200
    raw = client.get(
        f"/api/reports/{body['report_id']}/image/raw", headers=_auth(token)
    )
    assert raw.status_code == 200
    assert raw.content == PNG_BYTES


def test_report_rejects_invalid_severity(client):
    token = _login(client, "citizen@test.app")
    response = client.post(
        "/api/user/reports",
        data={
            "issue_type": "Waterlogging",
            "latitude": "22.5",
            "longitude": "88.3",
            "severity": "Catastrophic",
        },
        headers=_auth(token),
    )
    assert response.status_code == 422


def test_report_rejects_out_of_range_latitude(client):
    token = _login(client, "citizen@test.app")
    response = client.post(
        "/api/user/reports",
        data={
            "issue_type": "Waterlogging",
            "latitude": "122.5",
            "longitude": "88.3",
            "severity": "High",
        },
        headers=_auth(token),
    )
    assert response.status_code == 422


def test_my_reports_only_returns_own_reports(client):
    token = _login(client, "citizen@test.app")
    body = client.get("/api/user/reports", headers=_auth(token)).json()
    assert body["total"] >= 1
    assert all(item["user_id"] == "U1001" for item in body["items"])


def test_other_citizen_cannot_read_evidence_image(client):
    owner = _login(client, "citizen@test.app")
    report_id = client.get("/api/user/reports", headers=_auth(owner)).json()["items"][0][
        "report_id"
    ]
    other = _login(client, "new.citizen@test.app")
    response = client.get(f"/api/reports/{report_id}/image", headers=_auth(other))
    assert response.status_code == 403


def test_submitting_a_report_creates_a_notification(client):
    token = _login(client, "citizen@test.app")
    counts = client.get("/api/notifications/count", headers=_auth(token)).json()
    assert counts["unread"] >= 1
    listing = client.get("/api/notifications", headers=_auth(token)).json()
    assert listing["items"][0]["type"] == "report_submitted"


def test_user_home_summary_counts_come_from_the_database(client):
    token = _login(client, "citizen@test.app")
    body = client.get(
        "/api/user/home",
        params={"latitude": 22.5726, "longitude": 88.3639, "radius": 1000},
        headers=_auth(token),
    ).json()
    assert body["name"] == "Ananya Sen"
    assert body["ramps"] >= 1
    assert body["my_reports"] >= 1
    assert isinstance(body["latest_updates"], list)


# ---------------------------------------------------------------------------
# Authority CSV import
# ---------------------------------------------------------------------------
def test_csv_import_accepts_valid_rows(client):
    token = _login(client, "authority@test.app")
    csv_body = CSV_HEADER + (
        'RS-9001,U1042,Blocked Ramp,"College Street, Kolkata",22.5726,88.3639,High,'
        '"Ramp blocked by a parked vehicle.","https://example.com/RS-9001.jpg",'
        "2026-08-31T10:30:00+05:30,Needs Review,Submitted,Community\n"
        'RS-9002,U1043,Damaged Footpath,"Park Street, Kolkata",22.5535,88.3529,Medium,'
        '"Uneven footpath surface.","https://example.com/RS-9002.jpg",'
        "2026-08-30T15:20:00+05:30,Needs Review,Submitted,Community\n"
    )
    response = client.post(
        "/api/authority/reports/upload",
        files={"file": ("reports.csv", io.BytesIO(csv_body.encode()), "text/csv")},
        headers=_auth(token),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {
        "totalRows": 2,
        "successfulRows": 2,
        "failedRows": 0,
        "errors": [],
        "inserted": ["RS-9001", "RS-9002"],
    }


def test_csv_import_stores_image_url_verbatim_without_s3(client):
    token = _login(client, "authority@test.app")
    detail = client.get("/api/authority/reports/RS-9001", headers=_auth(token)).json()
    assert detail["image_url"] == "https://example.com/RS-9001.jpg"
    # No priority is assigned during import.
    assert detail["predicted_priority"] is None
    assert detail["final_priority"] is None


def test_csv_import_reports_row_level_errors(client):
    token = _login(client, "authority@test.app")
    csv_body = CSV_HEADER + (
        'RS-9010,U1,Ramp Blocked,"A",22.5,88.3,High,"Fine row.",,'
        "2026-08-20T10:00:00+05:30,Needs Review,Submitted,Community\n"
        'RS-9011,U2,Ramp Blocked,"B",122.5,88.3,High,"Bad latitude.",,'
        "2026-08-20T10:00:00+05:30,Needs Review,Submitted,Community\n"
        'RS-9012,U3,Ramp Blocked,"C",22.5,88.3,Critical,"Bad severity.",,'
        "2026-08-20T10:00:00+05:30,Needs Review,Submitted,Community\n"
        'RS-9010,U4,Ramp Blocked,"D",22.5,88.3,Low,"Duplicate in file.",,'
        "2026-08-20T10:00:00+05:30,Needs Review,Submitted,Community\n"
        'RS-9001,U5,Ramp Blocked,"E",22.5,88.3,Low,"Already in the database.",,'
        "2026-08-20T10:00:00+05:30,Needs Review,Submitted,Community\n"
    )
    body = client.post(
        "/api/authority/reports/upload",
        files={"file": ("mixed.csv", io.BytesIO(csv_body.encode()), "text/csv")},
        headers=_auth(token),
    ).json()
    assert body["totalRows"] == 5
    assert body["successfulRows"] == 1
    assert body["failedRows"] == 4
    reasons = {error["row"]: error["reason"] for error in body["errors"]}
    assert reasons[3] == "Invalid latitude"
    assert "severity" in reasons[4]
    assert "Duplicate report_id within the file" == reasons[5]
    assert "Duplicate report_id (already imported)" == reasons[6]


def test_csv_import_rejects_missing_columns(client):
    token = _login(client, "authority@test.app")
    response = client.post(
        "/api/authority/reports/upload",
        files={"file": ("bad.csv", io.BytesIO(b"report_id,issue_type\nRS-1,Ramp Blocked\n"), "text/csv")},
        headers=_auth(token),
    )
    assert response.status_code == 400
    assert "missing required column" in response.json()["detail"].lower()


def test_citizen_cannot_upload_csv(client):
    token = _login(client, "citizen@test.app")
    response = client.post(
        "/api/authority/reports/upload",
        files={"file": ("x.csv", io.BytesIO(CSV_HEADER.encode()), "text/csv")},
        headers=_auth(token),
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Authority dashboard, filters and validation
# ---------------------------------------------------------------------------
def test_dashboard_overview_is_computed_from_the_database(client):
    token = _login(client, "authority@test.app")
    body = client.get("/api/authority/overview", headers=_auth(token)).json()
    assert body["total_reports"] >= 4
    assert body["new_reports"] >= 1
    assert body["under_review"] >= 1
    assert 0.0 <= body["resolution_rate"] <= 100.0


def test_reports_search_and_filters(client):
    token = _login(client, "authority@test.app")
    by_id = client.get(
        "/api/authority/reports", params={"search": "RS-9001"}, headers=_auth(token)
    ).json()
    assert by_id["total"] == 1

    high = client.get(
        "/api/authority/reports", params={"severity": "High"}, headers=_auth(token)
    ).json()
    assert all(item["severity"] == "High" for item in high["items"])

    by_location = client.get(
        "/api/authority/reports", params={"location": "park street"}, headers=_auth(token)
    ).json()
    assert by_location["total"] >= 1


def test_manual_validation_updates_status_and_notifies(client):
    token = _login(client, "authority@test.app")
    citizen = _login(client, "citizen@test.app")
    report_id = client.get("/api/user/reports", headers=_auth(citizen)).json()["items"][0][
        "report_id"
    ]

    body = client.post(
        f"/api/authority/reports/{report_id}/validate",
        json={"validation_status": "Valid", "note": "Photo clearly shows the blockage."},
        headers=_auth(token),
    ).json()
    assert body["validation_status"] == "Valid"
    assert body["validated_by"] == "AU101"
    assert body["status"] == "Under Review"

    inbox = client.get("/api/notifications", headers=_auth(citizen)).json()
    assert inbox["items"][0]["type"] == "report_validated"


def test_validation_rejects_unknown_status(client):
    token = _login(client, "authority@test.app")
    response = client.post(
        "/api/authority/reports/RS-9001/validate",
        json={"validation_status": "Probably"},
        headers=_auth(token),
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# XGBoost priority recommendation and confirmation
# ---------------------------------------------------------------------------
def test_priority_prediction_and_human_confirmation(client):
    token = _login(client, "authority@test.app")
    prediction = client.post(
        "/api/authority/reports/RS-9001/priority/predict", headers=_auth(token)
    ).json()
    assert prediction["predicted_priority"] in ("Low", "Medium", "High", "Critical")
    assert 0.0 <= prediction["confidence"] <= 1.0
    assert prediction["model"] in ("xgboost", "sklearn-gbm", "rules")
    assert prediction["rationale"]

    # The recommendation is stored but is not final until a human confirms.
    detail = client.get("/api/authority/reports/RS-9001", headers=_auth(token)).json()
    assert detail["predicted_priority"] == prediction["predicted_priority"]
    assert detail["final_priority"] is None

    confirmed = client.post(
        "/api/authority/reports/RS-9001/priority/confirm",
        json={"final_priority": "Critical"},
        headers=_auth(token),
    ).json()
    assert confirmed["final_priority"] == "Critical"
    assert confirmed["priority_confirmed_by"] == "AU101"


# ---------------------------------------------------------------------------
# Assignment -> maintenance -> verification
# ---------------------------------------------------------------------------
def test_full_maintenance_lifecycle(client):
    authority = _login(client, "authority@test.app")
    maintenance = _login(client, "maintenance@test.app")

    task = client.post(
        "/api/authority/reports/RS-9001/assign",
        json={"assigned_team": "Team Alpha", "assigned_to": "MN201"},
        headers=_auth(authority),
    )
    assert task.status_code == 201, task.text
    task_id = task.json()["task_id"]
    assert task.json()["status"] == "Assigned"

    # The report moves to Assigned.
    detail = client.get("/api/authority/reports/RS-9001", headers=_auth(authority)).json()
    assert detail["status"] == "Assigned"

    # A second assignment while one is open is refused.
    duplicate = client.post(
        "/api/authority/reports/RS-9001/assign",
        json={"assigned_team": "Team Bravo"},
        headers=_auth(authority),
    )
    assert duplicate.status_code == 409

    # The maintenance user sees the task.
    tasks = client.get("/api/maintenance/tasks", headers=_auth(maintenance)).json()
    assert task_id in [item["task_id"] for item in tasks["items"]]

    # Start work.
    started = client.post(
        f"/api/maintenance/tasks/{task_id}/status",
        json={"status": "In Progress", "maintenance_notes": "Team dispatched to site."},
        headers=_auth(maintenance),
    ).json()
    assert started["status"] == "In Progress"

    # Completion without a resolution photo is refused.
    premature = client.post(
        f"/api/maintenance/tasks/{task_id}/status",
        json={"status": "Completed"},
        headers=_auth(maintenance),
    )
    assert premature.status_code == 400

    # Upload the resolution photo, then complete.
    uploaded = client.post(
        f"/api/maintenance/tasks/{task_id}/resolution",
        files={"photo": ("fixed.png", io.BytesIO(PNG_BYTES), "image/png")},
        data={"maintenance_notes": "Vehicle removed and bollards installed."},
        headers=_auth(maintenance),
    ).json()
    assert uploaded["has_resolution_image"] is True

    completed = client.post(
        f"/api/maintenance/tasks/{task_id}/status",
        json={"status": "Completed"},
        headers=_auth(maintenance),
    ).json()
    assert completed["status"] == "Completed"

    # A maintenance user cannot self-verify.
    forbidden = client.post(
        f"/api/maintenance/tasks/{task_id}/status",
        json={"status": "Verified"},
        headers=_auth(maintenance),
    )
    assert forbidden.status_code == 403

    # The authority verifies the resolution, closing the report.
    verified = client.post(
        f"/api/authority/tasks/{task_id}/verify",
        json={"approved": True, "notes": "Site photo confirms the ramp is clear."},
        headers=_auth(authority),
    ).json()
    assert verified["status"] == "Verified"

    closed = client.get("/api/authority/reports/RS-9001", headers=_auth(authority)).json()
    assert closed["status"] == "Resolved"

    # The reporter is notified.  RS-9001 came from the CSV import, so its
    # reporter is U1042 rather than the signed-in citizen; assert against the
    # notification actually written for that user.
    with SessionLocal() as db:
        rows = (
            db.execute(
                select(Notification).where(
                    Notification.report_id == "RS-9001",
                    Notification.type == "report_resolved",
                )
            )
            .scalars()
            .all()
        )
    assert [row.user_id for row in rows] == ["U1042"]


def test_authority_can_send_a_resolution_back_for_rework(client):
    authority = _login(client, "authority@test.app")
    maintenance = _login(client, "maintenance@test.app")

    task_id = client.post(
        "/api/authority/reports/RS-9002/assign",
        json={"assigned_team": "Team Alpha", "assigned_to": "MN201"},
        headers=_auth(authority),
    ).json()["task_id"]

    client.post(
        f"/api/maintenance/tasks/{task_id}/resolution",
        files={"photo": ("fixed.png", io.BytesIO(PNG_BYTES), "image/png")},
        headers=_auth(maintenance),
    )
    client.post(
        f"/api/maintenance/tasks/{task_id}/status",
        json={"status": "Completed"},
        headers=_auth(maintenance),
    )
    rejected = client.post(
        f"/api/authority/tasks/{task_id}/verify",
        json={"approved": False, "notes": "The photo does not show the full ramp."},
        headers=_auth(authority),
    ).json()
    assert rejected["status"] == "In Progress"
    assert rejected["completed_at"] is None


def test_maintenance_cannot_open_another_teams_task(client):
    authority = _login(client, "authority@test.app")
    maintenance = _login(client, "maintenance@test.app")
    task_id = client.post(
        "/api/authority/reports/RS-9010/assign",
        json={"assigned_team": "Drainage Unit", "assigned_to": None},
        headers=_auth(authority),
    ).json()["task_id"]
    response = client.get(f"/api/maintenance/tasks/{task_id}", headers=_auth(maintenance))
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Analytics and audit
# ---------------------------------------------------------------------------
def test_analytics_breakdowns(client):
    token = _login(client, "authority@test.app")
    body = client.get("/api/analytics", params={"days": 30}, headers=_auth(token)).json()
    assert body["total_reports"] >= 4
    assert body["by_issue_type"]
    assert body["by_severity"]
    assert len(body["trend"]) == 30


def test_analytics_map_pins(client):
    token = _login(client, "authority@test.app")
    pins = client.get("/api/analytics/map", headers=_auth(token)).json()
    assert pins
    assert {"report_id", "latitude", "longitude", "severity"} <= set(pins[0])


def test_audit_trail_records_authority_actions(client):
    token = _login(client, "authority@test.app")
    entries = client.get("/api/authority/audit", headers=_auth(token)).json()
    actions = {entry["action"] for entry in entries}
    assert {"report.validate", "report.csv_import", "task.assign"} <= actions
