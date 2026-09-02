# RouteSathi

**Accessible Places. Better Access.**

RouteSathi is a location-based accessibility platform for cities. Citizens discover
accessible places near them and report the barriers that block them; a municipal
authority validates those reports, prioritises them and assigns repairs; a maintenance
team carries out the work and submits photographic proof, which the authority verifies
before the citizen's report is closed.

This repository contains a **working MVP** — a real full-stack application, not a UI
prototype. Every number on every screen is computed from the database.

---

## Table of contents

1. [Project purpose](#1-project-purpose)
2. [Architecture](#2-architecture)
3. [MVP scope](#3-mvp-scope)
4. [Technology stack](#4-technology-stack)
5. [Repository layout](#5-repository-layout)
6. [Local development](#6-local-development)
7. [Database setup (Neon + PostGIS)](#7-database-setup-neon--postgis)
8. [Image storage](#8-image-storage)
9. [Authentication](#9-authentication)
10. [API documentation](#10-api-documentation)
11. [CSV import format](#11-csv-import-format)
12. [Machine learning: priority recommendation](#12-machine-learning-priority-recommendation)
13. [Deployment](#13-deployment)
14. [Git workflow](#14-git-workflow)
15. [Testing](#15-testing)

---

## 1. Project purpose

Accessibility information about public space is scattered, stale, or simply missing, and
the barriers that appear day to day — a van parked across a ramp, a flooded footpath, a
crossing blocked by hoarding — have nowhere to be reported and no visible route to being
fixed.

RouteSathi closes that loop:

| Role | What they do |
| --- | --- |
| **Citizen** | Find accessible ramps, entrances, toilets, parking, crossings and pathways nearby. Report a barrier with a photo, a location and a severity. Track it to completion. |
| **Authority** | Bulk-import reports, validate them manually, get an ML priority recommendation and confirm it, assign a maintenance team, and verify the repair. |
| **Maintenance** | See assigned tasks, update status, record notes, upload proof of the repair and submit it for verification. |

## 2. Architecture

```
                            ROUTESATHI
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
      USER PORTAL         AUTHORITY PORTAL     MAINTENANCE PORTAL
     (mobile-first)          (desktop)             (desktop)
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                ▼
                        FASTAPI BACKEND
                    (one app, /api/* on Vercel)
                                │
             ┌──────────────────┼──────────────────┐
             ▼                  ▼                  ▼
      NEON PostgreSQL       Amazon S3          XGBoost
        + PostGIS        evidence images   priority prediction
```

All three portals are served from **one React SPA** and talk to **one FastAPI
application** over same-origin `/api/...` paths, from one GitHub repository: the
frontend on Vercel, the API on Render, with Vercel proxying `/api/*` to Render.

### Report lifecycle

```
 Citizen submits ──▶ Needs Review ──▶ Authority validates ──▶ Valid
                                                                │
                          XGBoost recommends priority ◀─────────┤
                                       │                        │
                          Authority confirms priority           │
                                       │                        │
                                       ▼                        │
                            Assigned to a team ─────────────────┘
                                       │
                            Maintenance: In Progress
                                       │
                     Resolution photo uploaded (S3) → Completed
                                       │
                            Authority verifies → Resolved
                                       │
                     ┌─────────────────┴─────────────────┐
                     ▼                                   ▼
          Citizen notified            That place becomes a VERIFIED
                                      accessible facility — green on
                                      the map instead of a red issue
```

### The map follows the workflow

A report is not just a ticket, it is a statement about a place, so both ends of
the workflow move the accessibility map:

| Event | Effect on the map |
| --- | --- |
| Citizen submits a report | Red issue marker appears. Known facilities are untouched — an unreviewed report does not change the record. |
| Authority marks it **Valid** | The facility at that spot turns **red (Blocked)**. Citizens stop being pointed at a ramp that does not work. |
| Maintenance completes the repair | Still red. Nothing changes until a human verifies it. |
| Authority **verifies** the repair | The facility turns **green (Verified)**, and the issue marker disappears. If no facility existed there — a ramp that was built where there were only stairs — one is created. |

Matching is spatial: a facility of the same kind within 40 m of the report is
treated as the same place, so repeated reports about one ramp update a single
facility instead of littering the map with duplicates.

## 3. MVP scope

**Included**

- Citizen: signup/login, current location, accessibility map, nearby search, facility
  categories and details, issue reporting with image evidence, severity, automatic
  timestamp, My Reports, report status, notifications, profile.
- Authority: dashboard overview, optional CSV import for reports gathered outside the
  app, reports list, search and filters, report details, manual validation, priority
  recommendation and confirmation, maintenance assignment, resolution verification,
  map and analytics.
- Maintenance: separate login, assigned tasks, task details, status updates, notes,
  resolution image upload, completion submission.

**Deliberately out of scope for this MVP**

There is **no routing engine**. The map is used for location, discovery, nearby search,
report placement and issue visualisation only. Specifically, this MVP does *not*
implement source-to-destination accessibility routing, turn-by-turn navigation,
wheelchair route calculation, route optimisation, or traffic-aware routing. Distances
shown are straight-line (great-circle) distances in metres, never walking distances.

## 4. Technology stack

**Frontend** — React 18, JavaScript, Vite, React Router, Axios, Leaflet, hand-written
CSS (no UI framework). HTML5 and CSS3 throughout.

**Backend** — Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, psycopg 3, Uvicorn (for
local development), python-multipart, PyJWT, bcrypt, boto3, pandas, scikit-learn,
XGBoost.

**Data** — Neon PostgreSQL with the PostGIS extension. Amazon S3 for image objects.

**Deployment** — GitHub → Vercel (static build + Python serverless function).

## 5. Repository layout

```
routesathi-mvp/
├── api/
│   └── index.py               Vercel Python entrypoint (exports the FastAPI `app`)
├── backend/
│   ├── core/                  config, constants, security, dependencies
│   ├── db/                    engine/session, PostGIS bootstrap, spatial queries
│   ├── models/                SQLAlchemy models
│   ├── schemas/               Pydantic request/response models
│   ├── services/              S3 storage, CSV import, notifications, audit
│   ├── ml/                    XGBoost priority model and features
│   ├── routers/               auth, users, facilities, reports, authority,
│   │                          maintenance, notifications, analytics
│   ├── utils/                 ids, datetimes, error formatting
│   └── main.py                FastAPI application factory
├── app/src/                   React frontend
│   ├── api/                   axios client and endpoint wrappers
│   ├── components/            shells, map, badges, shared UI
│   ├── context/               auth and toast providers
│   ├── pages/                 user/, authority/, maintenance/
│   └── styles/                theme, components, portal, map
├── data/                      sample CSV fixtures
├── docs/                      architecture, API, database, S3, deployment, git
├── public/                    static assets
├── scripts/seed_data.py       demo data seeder
├── tests/test_api.py          end-to-end API tests
├── index.html                 Vite entry document
├── package.json  vite.config.js  vercel.json
├── requirements.txt
└── .env.example
```

The internal Python packages live under `backend/` rather than inside `api/`, because
Vercel treats **every** `.py` file in `api/` as its own serverless function. Keeping a
single `api/index.py` entrypoint that imports from `backend/` gives one function, one
cold start and one shared connection pool.

## 6. Local development

**Prerequisites:** Python 3.11+, Node 18+.

```bash
git clone https://github.com/<owner>/routesathi-mvp.git
cd routesathi-mvp

# 1. Backend dependencies
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# for the test suite as well:
# pip install -r requirements-dev.txt

# 2. Frontend dependencies
npm install

# 3. Environment
cp .env.example .env               # then edit .env
```

`.env` is optional to get started: with no `DATABASE_URL` the API falls back to a local
SQLite file, and with no AWS credentials it stores uploads in the database. Both
fallbacks exist so the project runs immediately after a clone; production uses Neon and
S3.

```bash
# 4. Seed demo accounts, facilities, reports and tasks
python scripts/seed_data.py

# 5. Run the API (terminal 1)
npm run api                        # uvicorn api.index:app --reload --port 8000

# 6. Run the frontend (terminal 2)
npm run dev                        # http://localhost:5173
```

Vite proxies `/api` to `http://127.0.0.1:8000`, so the frontend uses the same
same-origin paths locally as it does in production.

### Demo accounts

All seeded accounts share the password `Password123!` (override with
`SEED_DEFAULT_PASSWORD`).

| Portal | Email |
| --- | --- |
| Citizen | `ananya@routesathi.app` |
| Authority | `authority@routesathi.app` |
| Maintenance | `maintenance@routesathi.app` |

### Useful commands

| Command | What it does |
| --- | --- |
| `npm run dev` | Vite dev server with the `/api` proxy |
| `npm run build` | Production build into `dist/` |
| `npm run api` | FastAPI with auto-reload on port 8000 |
| `npm run seed` | Seed the database |
| `npm run test:api` | Run the API test suite |

## 7. Database setup (Neon + PostGIS)

1. Create a project at [neon.com](https://neon.com) and copy the connection string.
2. Put it in `.env` as `DATABASE_URL`. Use the **pooled** endpoint in production —
   serverless functions open many short-lived connections.

```
DATABASE_URL=postgresql+psycopg://user:password@ep-xxxx-pooler.region.aws.neon.tech/routesathi?sslmode=require
```

`postgresql://` and `postgres://` URLs are rewritten to use the psycopg 3 driver
automatically, so you can paste Neon's string unchanged.

3. Start the API once. On first connection it runs an **idempotent bootstrap** that:
   - creates every table from the SQLAlchemy metadata,
   - runs `CREATE EXTENSION IF NOT EXISTS postgis;`,
   - converts `reports.location_point` and `accessibility_facilities.location_point`
     to `GEOGRAPHY(Point, 4326)`,
   - creates GiST indexes on both,
   - installs triggers that keep `location_point` in sync with the `latitude` /
     `longitude` columns the application writes,
   - backfills the geography for any existing rows.

`GET /api/health` reports `"spatial_backend": "postgis"` once this succeeds.

### Tables

`users`, `accessibility_facilities`, `reports`, `maintenance_tasks`, `notifications`,
`audit_logs` (plus `stored_files`, used only by the no-S3 development fallback). Full
column reference: [`docs/DATABASE.md`](docs/DATABASE.md).

### Spatial queries

Nearby search uses `ST_DWithin` against the geography column with `ST_Distance` for the
metre distance, index-accelerated by the GiST index:

```sql
SELECT facility_id, name, type, status,
       ST_Distance(location_point, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS distance_m
  FROM accessibility_facilities
 WHERE ST_DWithin(location_point, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius)
   AND type = :type
 ORDER BY distance_m ASC;
```

If PostGIS is unavailable, the identical API is served by an equivalent great-circle
expression in SQL with a bounding-box pre-filter, so the app degrades rather than
breaking. `GET /api/health` always tells you which path is active.

## 8. Image storage

Report evidence and resolution photos live in object storage. **Binary images never go
into PostgreSQL** — the database holds only the object key.

The storage layer speaks the S3 API, so any S3-compatible provider works with the same
variables. **Cloudflare R2 is the simplest and cheapest choice** — 10 GB free, no egress
fees, and an API token instead of an IAM policy:

```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=auto
S3_BUCKET=routesathi-media
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
```

Leave `S3_ENDPOINT_URL` empty to use Amazon S3 instead; Supabase Storage, Backblaze B2
and MinIO also work by pointing it at their endpoint.

Object key layout:

```
reports/2026/08/RS-1001-a1b2c3d4.jpg
resolutions/2026/08/RS-1001-fixed-e5f6a7b8.jpg
```

Buckets stay private. Reads are served through short-lived **presigned URLs** minted by
the API only after it has checked the caller's role and ownership:

```
PostgreSQL → FastAPI → object key → presigned URL → browser
```

`GET /api/health` names the provider it detected. With no credentials configured the API
falls back to storing images in the database so a fresh clone still works end to end —
development only. Full setup, including the five-step R2 walkthrough:
[`docs/STORAGE.md`](docs/STORAGE.md).

## 9. Authentication

JWT bearer tokens, HS256, with bcrypt password hashing.

```
POST /api/auth/login    → { access_token, token_type, expires_in, role, user }
POST /api/auth/signup   → same shape (citizen accounts only)
GET  /api/auth/me       → the current user
```

Send the token as `Authorization: Bearer <token>`.

Three roles — `USER`, `AUTHORITY`, `MAINTENANCE` — enforced by the FastAPI dependencies
`require_user`, `require_authority` and `require_maintenance`. The role is re-read from
the database on every request rather than trusted from the token, so a permission change
takes effect immediately.

The React app also has route guards, but **the backend dependencies are the security
boundary** — the guards only keep the UI coherent.

Notes on the security model:

- Self-service signup creates citizen accounts only. Authority and maintenance accounts
  are provisioned by an administrator.
- Login returns an identical error for an unknown email and a wrong password, so the
  endpoint cannot be used to enumerate registered addresses.
- Citizens can only read evidence attached to their own reports.
- Private images are delivered through short-lived, single-resource media tokens,
  because a browser cannot attach an `Authorization` header to an `<img>` tag. With S3
  configured, presigned URLs serve the same purpose.

## 10. API documentation

Interactive OpenAPI docs are served by the application itself:

- Swagger UI — `/api/docs`
- ReDoc — `/api/redoc`
- Schema — `/api/openapi.json`

A complete endpoint reference is in [`docs/API.md`](docs/API.md). The main routes:

| Method | Path | Role | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/auth/login` | — | Sign in, receive a JWT |
| `POST` | `/api/auth/signup` | — | Register a citizen account |
| `GET` | `/api/user/home` | USER | Home-screen counts and latest updates |
| `GET` | `/api/facilities/nearby` | any | PostGIS radius search |
| `GET` | `/api/facilities/{id}` | any | Facility details |
| `POST` | `/api/user/reports` | USER | Submit a report (multipart, with photo) |
| `GET` | `/api/user/reports` | USER | My Reports |
| `GET` | `/api/reports/{id}/image` | any | Short-lived evidence image link |
| `GET` | `/api/notifications` | any | Notification inbox |
| `GET` | `/api/authority/overview` | AUTHORITY | Dashboard counters |
| `POST` | `/api/authority/reports/upload` | AUTHORITY | CSV bulk import |
| `GET` | `/api/authority/reports` | AUTHORITY | Filterable reports list |
| `POST` | `/api/authority/reports/{id}/validate` | AUTHORITY | Manual validation |
| `POST` | `/api/authority/reports/{id}/priority/predict` | AUTHORITY | XGBoost recommendation |
| `POST` | `/api/authority/reports/{id}/priority/confirm` | AUTHORITY | Human confirmation |
| `POST` | `/api/authority/reports/{id}/assign` | AUTHORITY | Create a maintenance task |
| `POST` | `/api/authority/tasks/{id}/verify` | AUTHORITY | Verify or reject a repair |
| `GET` | `/api/analytics` | AUTHORITY | Aggregations and trend |
| `GET` | `/api/maintenance/tasks` | MAINTENANCE | Assigned task queue |
| `POST` | `/api/maintenance/tasks/{id}/status` | MAINTENANCE | Status update |
| `POST` | `/api/maintenance/tasks/{id}/resolution` | MAINTENANCE | Upload proof of repair |
| `GET` | `/api/health` | — | Which database, spatial, storage and ML backends are live |

Example — nearby ramps within 300 m:

```
GET /api/facilities/nearby?latitude=22.5726&longitude=88.3639&radius=300&type=Ramp
```

```json
[
  {
    "facility_id": "FAC-1",
    "name": "College Street Ramp",
    "type": "Ramp",
    "status": "Verified",
    "latitude": 22.5745,
    "longitude": 88.3639,
    "distance": 211.3
  }
]
```

## 11. CSV import format

Bulk import lives on the **authority dashboard** (the portal's first page), not on the
reports page.

```
report_id,user_id,issue_type,location,latitude,longitude,severity,description,image_url,timestamp,validation_status,status,source
```

```
RS-1001,U1042,Blocked Ramp,"College Street, Kolkata",22.5726,88.3639,High,"Wheelchair ramp blocked by parked vehicle.","https://example.com/RS-1001.jpg",2026-08-31T10:30:00+05:30,Needs Review,Submitted,Community
```

There is **no priority column** — priority is recommended by the model later and
confirmed by a human, never imported.

Validation rules:

| Column | Rule |
| --- | --- |
| `report_id` | Required, unique in the file and in the database |
| `user_id` | Required |
| `issue_type` | Required; common aliases (`Blocked Ramp`, `Damaged Footpath`, …) are mapped to canonical types |
| `latitude` | Required, −90 to 90 |
| `longitude` | Required, −180 to 180 |
| `severity` | Required; `Low`, `Medium`, `High` |
| `description` | Required |
| `timestamp` | Required; ISO-8601 and several common formats accepted |
| `validation_status` | Required; `Needs Review`, `Valid`, `Invalid` |
| `status` | Required; `Submitted`, `Under Review`, `Assigned`, `In Progress`, `Resolved` |
| `source` | Required |
| `image_url` | **Optional**, stored verbatim as TEXT |

During CSV import there is no S3 upload, no image processing and no ML inference.

Valid rows are committed; invalid rows are returned with a row number and a reason:

```json
{
  "totalRows": 10,
  "successfulRows": 9,
  "failedRows": 1,
  "errors": [
    { "row": 7, "reportId": "RS-1007", "reason": "Invalid latitude" }
  ]
}
```

Try it with [`data/sample_reports.csv`](data/sample_reports.csv) and
[`data/sample_reports_with_errors.csv`](data/sample_reports_with_errors.csv).
See [`docs/CSV.md`](docs/CSV.md).

## 12. Machine learning: priority recommendation

An **XGBoost** multiclass classifier recommends a priority (`Low` / `Medium` / `High` /
`Critical`) for a report. The recommendation is advisory: an authority reviewer must
confirm or override it, and only the confirmed value becomes `final_priority`. Both are
stored, so overrides are measurable.

Features: issue-type impact weight and one-hot, severity ordinal, source trust, whether
photo evidence is attached, description length and word count, report age, hour of day,
weekend flag, and validation state.

On first use the model trains on a deterministic, reproducible labelled corpus and
caches the booster in `ML_MODEL_DIR` (default `/tmp/routesathi-ml`), so warm containers
reuse it. If XGBoost is unavailable the service falls back to scikit-learn gradient
boosting, and then to a deterministic rule engine. Every response names the backend that
produced it, and so does `GET /api/health`.

Set `ML_ENABLED=0` to use the rule engine exclusively. See [`docs/ML.md`](docs/ML.md).

## 13. Deployment

Three supported paths. Pick one:

| | What runs where | Best for |
| --- | --- | --- |
| **AWS EC2** *(primary)* | Everything on one instance: nginx + FastAPI + PostgreSQL/PostGIS, photos in S3 | Full control, one bill, real XGBoost |
| Render + Vercel | API on Render, frontend on Vercel | No server to manage |
| Vercel only | Frontend and API as functions, ML dropped | Simplest, no XGBoost in production |

### AWS EC2 — one instance runs the whole product

```
Browser ──:80──▶  nginx ──┬─ /       → dist/ (React build)
                          └─ /api/*  → gunicorn → FastAPI + XGBoost
                                                      │
                          PostgreSQL 16 + PostGIS ◀────┤
                                                      ▼
                                                 Amazon S3
```

```bash
ssh ubuntu@<instance-ip>
sudo apt-get update && sudo apt-get install -y git
sudo git clone https://github.com/Nsi442/route_sathi.git /opt/routesathi
sudo bash /opt/routesathi/deploy/setup-ec2.sh
```

The script installs everything, creates the database and PostGIS extension,
builds the frontend, generates a JWT secret and database password into a
root-owned `chmod 600` file outside the repository, and starts the API behind
nginx. It is idempotent, so re-running it is also how you deploy updates.

**Attach an IAM role to the instance for S3** rather than putting keys on the
box — then the only storage config is `S3_BUCKET`, `AWS_REGION` and
`AWS_USE_INSTANCE_ROLE=1`, and AWS rotates the credentials itself.

Full guide, including sizing, HTTPS and troubleshooting:
[`docs/EC2.md`](docs/EC2.md). Deployment assets live in
[`deploy/`](deploy/).

### The other two paths

Render + Vercel keeps XGBoost and needs no server administration —
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md). Vercel alone is simplest but cannot
fit the ML stack in a serverless function, so priority falls back to the rule
engine with no code change (89.7% identical bands, never more than one apart).

## 14. Git workflow

Long-lived branches:

- `main` — production; every commit is deployable.
- `develop` — integration branch for the next release.

Feature branches off `develop`:

```
feature/user-portal      feature/map          feature/reporting
feature/authority        feature/maintenance  feature/xgboost
feature/database         feature/cloud
```

```bash
git checkout develop && git pull
git checkout -b feature/map
# ... work, commit ...
git push -u origin feature/map
# open a pull request into develop
```

Release: `develop` → `main` by pull request. Hotfixes branch from `main` and merge into
both.

**Never commit** `.env`, AWS credentials, the JWT secret, the Neon password or any
private key. `.gitignore` covers these; `.env.example` documents every variable with
placeholder values. More in [`docs/GIT_WORKFLOW.md`](docs/GIT_WORKFLOW.md).

## 15. Testing

```bash
pip install -r requirements-dev.txt
npm run test:api                     # or: pytest -q
```

The suite runs the full application against a throwaway database and covers
authentication and role enforcement, spatial radius search, report submission with photo
evidence, media-token scoping, CSV import including every row-level error, manual
validation, priority prediction and confirmation, the complete assignment → repair →
verification lifecycle, and analytics.

---

## License

MIT — see [LICENSE](LICENSE).
