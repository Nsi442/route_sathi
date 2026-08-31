# Architecture

## Shape of the system

One React single-page application serves three role-based portals. One FastAPI
application serves all of them over same-origin `/api/...` paths. One GitHub repository
deploys the frontend to Vercel and the API to Render, with Vercel proxying `/api/*` to
Render server-side so the browser still sees a single origin.

```
                            ROUTESATHI
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
      USER PORTAL         AUTHORITY PORTAL     MAINTENANCE PORTAL
     (mobile-first)          (desktop)             (desktop)
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                ▼
                        FASTAPI BACKEND
                                │
             ┌──────────────────┼──────────────────┐
             ▼                  ▼                  ▼
      NEON PostgreSQL       Amazon S3          XGBoost
        + PostGIS        evidence images   priority prediction
```

The three portals share one backend, one auth system, one report table and one facility
table. A report submitted in the citizen app is the same row the authority validates and
the maintenance team repairs — there is no synchronisation between systems because there
is only one system.

## Backend layering

```
api/index.py                  Vercel entrypoint; exposes the FastAPI app
  └── backend/main.py         application factory, CORS, error handling, /health
        ├── routers/          HTTP layer: validation, status codes, responses
        ├── services/         storage, CSV import, notifications, audit, serializers
        ├── ml/               feature extraction and the priority model
        ├── models/           SQLAlchemy ORM
        ├── schemas/          Pydantic request/response contracts
        ├── db/               engine, PostGIS bootstrap, spatial queries
        ├── core/             config, constants, security, role dependencies
        └── utils/            IDs, timestamps, error formatting
```

Routers own the transaction: services flush, routers commit. That keeps a request that
touches several tables — assigning a task writes the task, updates the report, pushes
notifications and records an audit entry — atomic without a service layer that has to
know about transaction scope.

## Design decisions worth explaining

### One ASGI entrypoint, not eight files

`api/` holds a single `index.py` that imports the routers from `backend/`, rather than
one file per resource. On a serverless host every `.py` file in `api/` becomes its own
function — eight files would mean eight cold starts, eight connection pools and eight
copies of the ML stack. The single entrypoint also runs unchanged under
`uvicorn api.index:app`, which is exactly how it runs on Render today.

The API ended up on Render rather than as a Vercel function because the XGBoost stack
installs at roughly 948 MB, well past the ~250 MB serverless limit. Dropping the ML
packages brings it to 98 MB and it deploys to Vercel unchanged, falling back to the
rule engine — see [DEPLOYMENT.md](DEPLOYMENT.md).

### Latitude/longitude authoritative, geography derived

The application writes plain `latitude` / `longitude` columns; a PostgreSQL trigger
derives `location_point` as `GEOGRAPHY(Point, 4326)`. The ORM stays portable, PostGIS
gets a real indexed column, and there is no way for the two to drift apart.

### A spatial abstraction with two backends

`backend/db/geo.py` exposes one `nearby()` function. On PostGIS it emits
`ST_DWithin` / `ST_Distance`; without it, an equivalent haversine expression with a
bounding-box pre-filter. The API contract is identical either way, so a Neon project
without the extension degrades in performance rather than breaking. `/api/health`
reports which path is live.

### Priority is recommended, never decided

The model writes `predicted_priority` and `prediction_confidence`. Only a human writes
`final_priority`. Both are kept, so disagreement between the model and reviewers is a
measurable quantity — and the confirmed values become the training set that eventually
replaces the synthetic corpus.

### Media tokens

Private images cannot be loaded by an `<img>` tag pointed at a protected endpoint,
because the browser will not send the `Authorization` header. With S3 the API mints a
presigned URL; without it, a short-lived token scoped to exactly one report or task. The
client fetches a link, then loads it — the same shape in both cases, so the frontend
does not branch on deployment configuration.

### Role checks in the backend

React route guards keep the UI coherent, but every protected endpoint depends on
`require_user`, `require_authority` or `require_maintenance`, and the role is re-read
from the database rather than trusted from the JWT. A permission change takes effect on
the next request.

## Request flows

### Citizen submits a report

```
React (multipart)
  → POST /api/user/reports
  → require_user
  → validate through the same Pydantic model the JSON route uses
  → photo → S3 (reports/YYYY/MM/RS-####-<rand>.jpg)
  → INSERT reports (report_id, user_id, Needs Review, Submitted, Citizen App)
  → INSERT notifications, INSERT audit_logs
  → commit → 201
```

### Authority imports a CSV

```
React (multipart)
  → POST /api/authority/reports/upload
  → require_authority
  → decode, sniff dialect, normalise headers
  → per row: validate, check duplicates in file and in database
  → INSERT valid rows; collect (row, reportId, reason) for the rest
  → audit entry with the row counts
  → commit → { totalRows, successfulRows, failedRows, errors }
```

### Repair lifecycle

```
Authority validates          reports.validation_status = Valid
Model recommends             reports.predicted_priority, prediction_confidence
Authority confirms           reports.final_priority
Authority assigns            INSERT maintenance_tasks; reports.status = Assigned
Maintenance starts           tasks.status = In Progress; reports.status = In Progress
Maintenance uploads proof    S3 resolutions/…; tasks.resolution_image_object_key
Maintenance submits          tasks.status = Completed  (blocked without a photo)
Authority verifies           tasks.status = Verified;  reports.status = Resolved
Citizen notified             INSERT notifications
```

Every transition writes an audit entry and, where the citizen is affected, a
notification.

## Frontend structure

```
app/src/
├── api/           axios instance (baseURL '/api') + endpoint wrappers
├── context/       AuthContext (JWT, session restore), ToastContext
├── components/    UserShell, ConsoleShell, MapView, Badge, CsvUpload, guards, UI
├── pages/
│   ├── user/          mobile-first citizen screens
│   ├── authority/     desktop dashboard, reports, detail, maintenance, analytics
│   └── maintenance/   desktop task queue and task detail
└── styles/        theme (tokens), components, portal (shells), map
```

Two shells carry the two form factors: `UserShell` renders a phone-width frame with a
bottom tab bar, `ConsoleShell` a navy sidebar with a white top bar that collapses to a
drawer under 900px. Both draw from the same token file, which is what keeps a
"Needs Review" badge identical in the citizen app and the authority table.

A single axios instance holds the bearer token and a 401 interceptor, so session expiry
signs the user out once rather than per component.

## Accessibility

The product is about accessibility, so the interface has to hold up:

- Visible focus rings on every interactive element.
- Semantic landmarks and skip links in both shells.
- Status conveyed by text and shape, never colour alone; badges pair a dot with a label.
- `aria-pressed` on filter chips and segmented controls; `aria-live` on toasts.
- Screen-reader prefixes on badges ("Severity: High").
- Labelled form controls throughout, with errors tied to their field.
- `prefers-reduced-motion` honoured.
- Colour pairings chosen for WCAG AA contrast on light backgrounds.

## What is deliberately absent

No routing engine, no turn-by-turn navigation, no wheelchair route calculation, no route
optimisation, no traffic awareness. The map is for locating yourself, discovering
facilities, placing a report and visualising issues. Distances are straight-line metres
and are labelled as such.
