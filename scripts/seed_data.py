#!/usr/bin/env python
"""Seed the database with demo accounts, accessibility facilities and reports.

    python scripts/seed_data.py            # create everything that is missing
    python scripts/seed_data.py --reset    # drop and recreate every table first

The generated accounts all share ``SEED_DEFAULT_PASSWORD`` (default
``Password123!``).  Never run this against a production database.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402

from backend.core.config import settings  # noqa: E402
from backend.core.security import hash_password  # noqa: E402
from backend.db.base import Base  # noqa: E402
from backend.db.init_db import init_db  # noqa: E402
from backend.db.session import SessionLocal, engine  # noqa: E402
from backend.models.entities import (  # noqa: E402
    AccessibilityFacility,
    MaintenanceTask,
    Report,
    User,
)
from backend.services import notifications  # noqa: E402
from backend.utils.datetimes import utcnow  # noqa: E402

RNG = random.Random(20260831)

ACCOUNTS = [
    # (user_id, name, email, phone, role, organisation, team)
    ("U1001", "Ananya Sen", "ananya@routesathi.app", "+91 98300 11001", "USER", None, None),
    ("U1002", "Rahul Das", "rahul@routesathi.app", "+91 98300 11002", "USER", None, None),
    ("U1003", "Meera Iyer", "meera@routesathi.app", "+91 98300 11003", "USER", None, None),
    (
        "AU101",
        "Kolkata Municipal Corporation",
        "authority@routesathi.app",
        "+91 33 2286 1000",
        "AUTHORITY",
        "Kolkata Municipal Corporation",
        None,
    ),
    (
        "AU102",
        "S. Bhattacharya",
        "authority2@routesathi.app",
        "+91 33 2286 1002",
        "AUTHORITY",
        "Accessibility Cell, KMC",
        None,
    ),
    (
        "MN201",
        "Team Alpha Lead",
        "maintenance@routesathi.app",
        "+91 98300 22001",
        "MAINTENANCE",
        "KMC Works Department",
        "Team Alpha",
    ),
    (
        "MN202",
        "Team Bravo Lead",
        "maintenance2@routesathi.app",
        "+91 98300 22002",
        "MAINTENANCE",
        "KMC Works Department",
        "Team Bravo",
    ),
]

# (name, type, lat, lng, status, description, address)
FACILITIES = [
    ("College Street Ramp", "Ramp", 22.5745, 88.3639, "Verified",
     "Concrete wheelchair ramp at the north gate with handrails on both sides.",
     "College Street, Kolkata"),
    ("Presidency University Entrance", "Entrance", 22.5751, 88.3646, "Verified",
     "Step-free main entrance, automatic doors, 1.2 m clear width.",
     "College Street, Kolkata"),
    ("Park Street Metro Accessible Toilet", "Toilet", 22.5533, 88.3521, "Available",
     "Accessible toilet with grab bars near the south concourse.",
     "Park Street Metro, Kolkata"),
    ("Park Street Accessible Parking", "Parking", 22.5539, 88.3535, "Available",
     "Two reserved bays with 3.6 m access aisle, close to the lift lobby.",
     "Park Street, Kolkata"),
    ("Esplanade Crossing", "Crossing", 22.5644, 88.3510, "Verified",
     "Tactile paving with audible signal on both approaches.",
     "Esplanade, Kolkata"),
    ("Maidan Accessible Pathway", "Pathway", 22.5600, 88.3450, "Available",
     "Smooth 2 m wide pathway, no kerbs, suitable for wheelchairs.",
     "Maidan, Kolkata"),
    ("Salt Lake Sector V Ramp", "Ramp", 22.5726, 88.4331, "Under Review",
     "Ramp gradient is being re-surveyed after resurfacing works.",
     "Sector V, Salt Lake"),
    ("Salt Lake City Centre Entrance", "Entrance", 22.5807, 88.4092, "Verified",
     "Level entry from the drop-off point, lift to all floors.",
     "City Centre, Salt Lake"),
    ("New Market Accessible Toilet", "Toilet", 22.5615, 88.3520, "Blocked",
     "Currently locked for renovation; expected to reopen next quarter.",
     "New Market, Kolkata"),
    ("Howrah Bridge Approach Ramp", "Ramp", 22.5851, 88.3468, "Available",
     "Gentle gradient ramp on the Kolkata-side approach footpath.",
     "Howrah Bridge, Kolkata"),
    ("Gariahat Crossing", "Crossing", 22.5186, 88.3639, "Under Review",
     "Tactile paving worn; accessibility survey scheduled.",
     "Gariahat, Kolkata"),
    ("Science City Accessible Parking", "Parking", 22.5400, 88.3950, "Verified",
     "Four reserved bays adjacent to the accessible entrance.",
     "Science City, Kolkata"),
    ("Rabindra Sadan Entrance", "Entrance", 22.5432, 88.3441, "Available",
     "Portable ramp available on request at the box office.",
     "Rabindra Sadan, Kolkata"),
    ("Sealdah Station Pathway", "Pathway", 22.5675, 88.3707, "Under Review",
     "Pathway partially obstructed by vendor stalls during peak hours.",
     "Sealdah, Kolkata"),
    ("Jadavpur University Ramp", "Ramp", 22.4991, 88.3714, "Verified",
     "Ramp with handrails to the arts faculty building.",
     "Jadavpur, Kolkata"),
]

# (report_id, user_id, issue_type, location, lat, lng, severity, description, days_ago,
#  validation, status, source)
REPORTS = [
    ("RS-1001", "U1042", "Ramp Blocked", "College Street, Kolkata", 22.5726, 88.3639, "High",
     "Wheelchair ramp blocked by parked vehicle.", 0, "Needs Review", "Submitted", "Community"),
    ("RS-1002", "U1043", "Footpath Damaged", "Park Street, Kolkata", 22.5535, 88.3529, "Medium",
     "Uneven footpath surface makes wheelchair movement difficult.", 1,
     "Needs Review", "Submitted", "Community"),
    ("RS-1003", "U1044", "Waterlogging", "Salt Lake, Kolkata", 22.5726, 88.4331, "High",
     "Waterlogging blocks the accessible pathway.", 2, "Needs Review", "Submitted", "Community"),
    ("RS-1004", "U1001", "No Accessible Entrance", "New Market, Kolkata", 22.5615, 88.3520,
     "High", "The side entrance has three steps and no ramp or lift alternative.", 4,
     "Valid", "Under Review", "Citizen App"),
    ("RS-1005", "U1002", "Blocked Crossing", "Esplanade, Kolkata", 22.5644, 88.3510, "Medium",
     "Construction barriers block the tactile crossing on the east side.", 6,
     "Valid", "Assigned", "Citizen App"),
    ("RS-1006", "U1003", "Stairs / No Ramp", "Sealdah, Kolkata", 22.5675, 88.3707, "High",
     "Foot overbridge has stairs only; wheelchair users must cross on the road.", 8,
     "Valid", "In Progress", "Citizen App"),
    ("RS-1007", "U1001", "Footpath Damaged", "Gariahat, Kolkata", 22.5186, 88.3639, "Low",
     "Small cracks along the footpath near the market entrance.", 11,
     "Valid", "Resolved", "Citizen App"),
    ("RS-1008", "U1045", "Ramp Blocked", "Howrah Bridge, Kolkata", 22.5851, 88.3468, "Medium",
     "Vendor stall occupies the base of the approach ramp.", 13,
     "Needs Review", "Submitted", "Field Survey"),
    ("RS-1009", "U1002", "Waterlogging", "Jadavpur, Kolkata", 22.4991, 88.3714, "Medium",
     "Water collects at the ramp base after rain and stays for hours.", 15,
     "Valid", "Assigned", "Citizen App"),
    ("RS-1010", "U1046", "Other", "Maidan, Kolkata", 22.5600, 88.3450, "Low",
     "Accessible pathway signage has faded and is hard to read.", 18,
     "Invalid", "Under Review", "Community"),
    ("RS-1011", "U1003", "No Accessible Entrance", "Rabindra Sadan, Kolkata", 22.5432, 88.3441,
     "Medium", "No permanent ramp at the box office entrance.", 21,
     "Valid", "Resolved", "Citizen App"),
    ("RS-1012", "U1047", "Blocked Crossing", "Sector V, Salt Lake", 22.5726, 88.4331, "High",
     "Parked two-wheelers block the pedestrian crossing approach.", 24,
     "Needs Review", "Submitted", "Municipal"),
]


def seed_users(db) -> dict[str, User]:
    created = {}
    password = hash_password(settings.seed_default_password)
    for user_id, name, email, phone, role, organisation, team in ACCOUNTS:
        user = db.execute(select(User).where(User.user_id == user_id)).scalar_one_or_none()
        if user is None:
            user = User(
                user_id=user_id,
                name=name,
                email=email,
                phone=phone,
                password_hash=password,
                role=role,
                organisation=organisation,
                team=team,
                is_active=True,
            )
            db.add(user)
        created[user_id] = user
    db.flush()
    return created


def seed_facilities(db) -> int:
    added = 0
    for index, (name, ftype, lat, lng, status, description, address) in enumerate(
        FACILITIES, start=1
    ):
        facility_id = f"FAC-{index}"
        existing = db.execute(
            select(AccessibilityFacility).where(
                AccessibilityFacility.facility_id == facility_id
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(
            AccessibilityFacility(
                facility_id=facility_id,
                name=name,
                type=ftype,
                description=description,
                address=address,
                latitude=lat,
                longitude=lng,
                status=status,
                source="Municipal Survey 2026",
                last_updated=utcnow() - dt.timedelta(days=RNG.randint(1, 60)),
            )
        )
        added += 1
    db.flush()
    return added


def seed_reports(db) -> int:
    added = 0
    now = utcnow()
    for (
        report_id,
        user_id,
        issue_type,
        location,
        lat,
        lng,
        severity,
        description,
        days_ago,
        validation,
        status,
        source,
    ) in REPORTS:
        existing = db.execute(
            select(Report).where(Report.report_id == report_id)
        ).scalar_one_or_none()
        if existing is not None:
            continue
        timestamp = now - dt.timedelta(days=days_ago, hours=RNG.randint(0, 20))
        report = Report(
            report_id=report_id,
            user_id=user_id,
            issue_type=issue_type,
            location_text=location,
            latitude=lat,
            longitude=lng,
            description=description,
            severity=severity,
            timestamp=timestamp,
            validation_status=validation,
            validated_by="AU101" if validation != "Needs Review" else None,
            validated_at=timestamp + dt.timedelta(hours=6) if validation != "Needs Review" else None,
            status=status,
            source=source,
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(report)
        added += 1
    db.flush()
    return added


def seed_tasks(db) -> int:
    """Create maintenance tasks matching the seeded report statuses."""
    plan = [
        ("MT-5001", "RS-1005", "Team Alpha", "MN201", "Assigned", None),
        ("MT-5002", "RS-1006", "Team Bravo", "MN202", "In Progress",
         "Site inspected; a temporary ramp will be installed this week."),
        ("MT-5003", "RS-1007", "Team Alpha", "MN201", "Verified",
         "Footpath slab replaced and levelled."),
        ("MT-5004", "RS-1009", "Drainage Unit", None, "Assigned", None),
        ("MT-5005", "RS-1011", "Team Bravo", "MN202", "Verified",
         "Permanent ramp installed at the box office entrance."),
    ]
    added = 0
    now = utcnow()
    for task_id, report_id, team, assignee, task_status, notes in plan:
        existing = db.execute(
            select(MaintenanceTask).where(MaintenanceTask.task_id == task_id)
        ).scalar_one_or_none()
        if existing is not None:
            continue
        report = db.execute(
            select(Report).where(Report.report_id == report_id)
        ).scalar_one_or_none()
        if report is None:
            continue
        assigned_at = report.timestamp + dt.timedelta(days=1)
        task = MaintenanceTask(
            task_id=task_id,
            report_id=report_id,
            assigned_team=team,
            assigned_to=assignee,
            assigned_by="AU101",
            assigned_at=assigned_at,
            status=task_status,
            maintenance_notes=notes,
            completed_at=assigned_at + dt.timedelta(days=2)
            if task_status == "Verified"
            else None,
            verified_by="AU101" if task_status == "Verified" else None,
            verified_at=assigned_at + dt.timedelta(days=3)
            if task_status == "Verified"
            else None,
            created_at=assigned_at,
            updated_at=now,
        )
        db.add(task)
        added += 1
    db.flush()
    return added


def seed_notifications(db) -> int:
    added = 0
    for report in (
        db.execute(select(Report).where(Report.user_id.in_(("U1001", "U1002", "U1003"))))
        .scalars()
        .all()
    ):
        notifications.report_submitted(db, report.user_id, report.report_id, report.issue_type)
        added += 1
        if report.validation_status != "Needs Review":
            notifications.report_validated(
                db, report.user_id, report.report_id, report.validation_status
            )
            added += 1
        if report.status == "Resolved":
            notifications.report_resolved(db, report.user_id, report.report_id)
            added += 1
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the RouteSathi database")
    parser.add_argument(
        "--reset", action="store_true", help="drop and recreate every table first"
    )
    args = parser.parse_args()

    if args.reset:
        print("Dropping all tables ...")
        Base.metadata.drop_all(bind=engine)

    init_db(force=True)

    with SessionLocal() as db:
        users = seed_users(db)
        facilities = seed_facilities(db)
        reports = seed_reports(db)
        tasks = seed_tasks(db)
        notes = seed_notifications(db)
        db.commit()

    print(f"Database: {settings.database_url.split('@')[-1]}")
    print(f"  users         : {len(users)} ensured")
    print(f"  facilities    : {facilities} inserted")
    print(f"  reports       : {reports} inserted")
    print(f"  tasks         : {tasks} inserted")
    print(f"  notifications : {notes} created")
    print()
    print(f"Demo password for every seeded account: {settings.seed_default_password}")
    print("  citizen     : ananya@routesathi.app")
    print("  authority   : authority@routesathi.app")
    print("  maintenance : maintenance@routesathi.app")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
