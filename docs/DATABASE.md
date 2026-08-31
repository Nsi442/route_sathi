# Database

Neon PostgreSQL with the PostGIS extension. SQLAlchemy 2 models, psycopg 3 driver.

## Connection

```
DATABASE_URL=postgresql+psycopg://user:password@ep-xxxx-pooler.region.aws.neon.tech/routesathi?sslmode=require
```

`postgres://` and `postgresql://` prefixes are rewritten to `postgresql+psycopg://`
automatically, so Neon's connection string works unchanged.

Use the **pooled** endpoint in production. Serverless functions open many short-lived
connections; the engine is configured with a small recycled pool (`pool_size=1`,
`pool_recycle=280`, `pool_pre_ping=True`) to avoid holding stale sockets across freezes.

If `DATABASE_URL` is unset the API falls back to `sqlite:///./routesathi.db` so a fresh
clone runs with no configuration. That fallback is for development only.

## Bootstrap

`backend/db/init_db.py` runs once per cold start, guarded by a module-level flag. It is
idempotent and safe to re-run:

1. `Base.metadata.create_all()` creates any missing tables.
2. `CREATE EXTENSION IF NOT EXISTS postgis;`
3. For `reports` and `accessibility_facilities`:
   - alter `location_point` to `geography(Point, 4326)`,
   - `CREATE INDEX IF NOT EXISTS ... USING GIST (location_point)`,
   - create a `BEFORE INSERT OR UPDATE OF latitude, longitude` trigger that sets
     `location_point` from the lat/lng the application writes,
   - backfill `location_point` for existing rows.

Failures are logged, never fatal: without PostGIS the app keeps working on the haversine
path. `GET /api/health` reports which is live.

Latitude and longitude are the authoritative values written by the application;
`location_point` is derived and maintained by the trigger. That keeps the ORM portable
while giving PostGIS a real indexed geography column to query.

## Tables

### `users`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer | primary key |
| `user_id` | varchar(64) | unique, e.g. `U1001`, `AU101`, `MN201` |
| `name` | varchar(160) | |
| `email` | varchar(255) | unique, lowercased |
| `phone` | varchar(32) | nullable |
| `password_hash` | varchar(255) | bcrypt |
| `role` | varchar(32) | `USER` \| `AUTHORITY` \| `MAINTENANCE` |
| `organisation` | varchar(160) | shown in the back-office shells |
| `team` | varchar(120) | maintenance team membership |
| `is_active` | boolean | |
| `created_at` / `updated_at` | timestamptz | |

### `accessibility_facilities`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer | primary key |
| `facility_id` | varchar(64) | unique, e.g. `FAC-1` |
| `name` | varchar(200) | |
| `type` | varchar(40) | `Ramp`, `Entrance`, `Toilet`, `Parking`, `Crossing`, `Pathway`, `Other` |
| `description` | text | |
| `address` | varchar(300) | |
| `latitude` / `longitude` | double precision | |
| `location_point` | `geography(Point, 4326)` | trigger-maintained, GiST indexed |
| `status` | varchar(32) | `Verified`, `Available`, `Under Review`, `Blocked`, `Inactive` |
| `source` | varchar(80) | |
| `last_updated` | timestamptz | |
| `created_at` / `updated_at` | timestamptz | |

### `reports`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer | primary key |
| `report_id` | varchar(64) | unique, e.g. `RS-1001`; generated server-side |
| `user_id` | varchar(64) | reporter |
| `issue_type` | varchar(80) | one of the seven canonical issue types |
| `location_text` | varchar(300) | the CSV `location` column |
| `latitude` / `longitude` | double precision | |
| `location_point` | `geography(Point, 4326)` | trigger-maintained, GiST indexed |
| `description` | text | |
| `severity` | varchar(16) | `Low`, `Medium`, `High` |
| `image_object_key` | varchar(400) | S3 key for app-submitted evidence |
| `image_url` | text | external URL from CSV import |
| `timestamp` | timestamptz | when the issue was reported |
| `validation_status` | varchar(32) | `Needs Review`, `Valid`, `Invalid` |
| `validated_by` / `validated_at` | varchar(64) / timestamptz | |
| `predicted_priority` | varchar(16) | model recommendation |
| `prediction_confidence` | double precision | 0–1 |
| `final_priority` | varchar(16) | human-confirmed value |
| `priority_confirmed_by` / `priority_confirmed_at` | varchar(64) / timestamptz | |
| `status` | varchar(32) | `Submitted`, `Under Review`, `Assigned`, `In Progress`, `Resolved` |
| `source` | varchar(80) | |
| `created_at` / `updated_at` | timestamptz | |

Priority columns exist in the schema but are **never required at CSV import time** —
they stay null until a reviewer requests a recommendation and confirms it.

### `maintenance_tasks`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer | primary key |
| `task_id` | varchar(64) | unique, e.g. `MT-5001` |
| `report_id` | varchar(64) | the report being repaired |
| `assigned_team` | varchar(120) | |
| `assigned_to` | varchar(64) | optional individual assignee |
| `assigned_by` / `assigned_at` | varchar(64) / timestamptz | |
| `status` | varchar(32) | `Assigned`, `In Progress`, `Completed`, `Verified`, `Rejected` |
| `maintenance_notes` | text | |
| `resolution_image_object_key` | varchar(400) | S3 key for proof of repair |
| `resolution_image_url` | text | |
| `completed_at` | timestamptz | |
| `verified_by` / `verified_at` | varchar(64) / timestamptz | |
| `verification_notes` | text | |
| `created_at` / `updated_at` | timestamptz | |

### `notifications`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer | primary key |
| `notification_id` | varchar(64) | unique, e.g. `NT-1` |
| `user_id` | varchar(64) | recipient |
| `report_id` | varchar(64) | nullable link |
| `title` | varchar(160) | |
| `message` | text | |
| `type` | varchar(48) | `report_submitted`, `report_validated`, `report_assigned`, `report_in_progress`, `report_resolved`, `task_assigned`, `task_verified`, `task_rejected`, `system` |
| `is_read` | boolean | |
| `created_at` | timestamptz | |

### `audit_logs`

| Column | Type | Notes |
| --- | --- | --- |
| `id` | integer | primary key |
| `user_id` | varchar(64) | actor |
| `role` | varchar(32) | actor's role at the time |
| `action` | varchar(80) | e.g. `report.validate`, `task.assign` |
| `entity_type` | varchar(48) | `report`, `task`, `facility`, `user` |
| `entity_id` | varchar(64) | |
| `timestamp` | timestamptz | |
| `metadata` | text | JSON payload |

Every authority and maintenance action of consequence writes an audit entry: CSV
imports, validation decisions, priority predictions and confirmations, status changes,
assignments, resolution uploads, verifications and rejections.

### `stored_files` (development only)

Holds base64 image data when S3 is not configured, so the upload and serve flow works
end to end on a fresh clone. Production deployments with `S3_BUCKET` and AWS credentials
never write to this table.

## Spatial queries

`backend/db/geo.py` exposes one `nearby()` helper used by facility search, the map
report pins and the home-screen counts.

**With PostGIS:**

```sql
SELECT facility_id, name, type, status,
       ST_Distance(location_point, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS distance_m
  FROM accessibility_facilities
 WHERE location_point IS NOT NULL
   AND ST_DWithin(location_point, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius)
   AND type = :type
 ORDER BY distance_m ASC
 LIMIT :limit;
```

**Without PostGIS:** the same signature is served by a haversine expression in SQL,
preceded by a lat/lng bounding-box filter so the composite index is still used. Results
are identical to within floating-point noise.

`distance` is always a straight-line distance in metres. It is not a walking distance,
and this MVP computes no routes.

## Seeding

```bash
python scripts/seed_data.py            # add anything missing (idempotent)
python scripts/seed_data.py --reset    # drop and recreate every table first
```

Creates 7 accounts across the three roles, 15 accessibility facilities across Kolkata,
12 reports spanning every status, 5 maintenance tasks and the matching notifications.
Never run `--reset` against production.
