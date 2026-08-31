# API reference

Base path `/api`. Interactive docs at `/api/docs` (Swagger UI) and `/api/redoc`.

All authenticated requests send `Authorization: Bearer <token>`.

## Conventions

- Timestamps are ISO-8601 UTC. Naive input is interpreted as IST (`Asia/Kolkata`).
- Paginated responses: `{ items, total, page, page_size, pages }`.
- Errors: `{ "detail": "A readable message" }`. Validation failures (422) also carry an
  `errors` array.
- `distance` is always straight-line metres.

| Status | Meaning |
| --- | --- |
| 400 | Malformed request (bad file type, missing resolution photo) |
| 401 | Missing, invalid or expired token |
| 403 | Authenticated but the role or ownership check failed |
| 404 | Resource does not exist |
| 409 | Conflict (duplicate email, report already assigned) |
| 413 | Upload too large |
| 422 | Field validation failed |

## System

### `GET /api/health`

Reports which backends are actually in use — useful for confirming a deployment picked
up PostGIS and S3.

```json
{
  "status": "ok",
  "app": "RouteSathi API",
  "environment": "production",
  "database": "postgresql",
  "spatial_backend": "postgis",
  "object_storage": "s3",
  "ml_backend": "xgboost",
  "time": "2026-08-31T10:30:00Z"
}
```

### `GET /api`

Service metadata and the docs link.

## Authentication

### `POST /api/auth/signup`

Citizen accounts only; `role: "AUTHORITY"` or `"MAINTENANCE"` returns 403.

```json
{ "name": "Ananya Sen", "email": "ananya@example.com", "phone": "+91 98300 11001", "password": "Password123!" }
```

→ `201` with the token payload below.

### `POST /api/auth/login`

```json
{ "email": "ananya@example.com", "password": "Password123!", "role": "USER" }
```

`role` is optional. When present, the login is refused (403) if the account does not
hold that role — this is what makes the portal tabs on the sign-in screen meaningful.

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 43200,
  "role": "USER",
  "user": { "user_id": "U1001", "name": "Ananya Sen", "email": "ananya@example.com", "role": "USER" }
}
```

An unknown email and a wrong password return the same 401 message.

### `GET /api/auth/me` · `POST /api/auth/refresh`

Current user; exchange a valid token for a fresh one.

## Citizen — `USER`

### `GET /api/user/home`

Query: `latitude`, `longitude`, `radius` (default 1000 m). Without coordinates the
counts are city-wide, so the screen is useful before geolocation is granted.

```json
{
  "name": "Ananya Sen",
  "ramps": 3, "entrances": 2, "toilets": 1, "parking": 1, "issues": 4,
  "my_reports": 6, "unread_notifications": 2, "radius": 1000,
  "latest_updates": [
    { "report_id": "RS-1005", "issue_type": "Blocked Crossing", "location_text": "Esplanade, Kolkata", "status": "Assigned", "severity": "Medium", "timestamp": "2026-08-25T09:00:00Z" }
  ]
}
```

### `GET /api/user/profile` · `PATCH /api/user/profile` · `POST /api/user/password`

Read and update the profile; change the password (requires the current one).

### `POST /api/user/reports`

`multipart/form-data`. Fields: `issue_type`, `latitude`, `longitude`, `severity`,
`description`, `location_text`, `timestamp`, `photo`.

The client never supplies `report_id`, `user_id`, `validation_status` or `status` — the
backend assigns `RS-####`, the authenticated user, `Needs Review` and `Submitted`. The
photo is streamed to S3 and only its object key is stored.

→ `201` with the full report.

### `POST /api/user/reports/json`

JSON variant for submissions without a photo. Same body as the form fields.

### `GET /api/user/reports`

Query: `status`, `search`, `page`, `page_size`. Returns only the caller's own reports.

### `GET /api/user/reports/{report_id}`

One of the caller's reports, including the linked maintenance task when there is one.

## Facilities — any authenticated role

### `GET /api/facilities/nearby`

| Parameter | Notes |
| --- | --- |
| `latitude` | required, −90…90 |
| `longitude` | required, −180…180 |
| `radius` | metres, 25…20000, default 500 |
| `type` | optional category filter |
| `status` | optional status filter |
| `limit` | default 100 |

PostGIS `ST_DWithin` + `ST_Distance`, ordered nearest-first. Inactive facilities are
excluded unless a status filter asks for them.

```
GET /api/facilities/nearby?latitude=22.5726&longitude=88.3639&radius=300&type=Ramp
```

```json
[
  { "facility_id": "FAC-1", "name": "College Street Ramp", "type": "Ramp",
    "status": "Verified", "latitude": 22.5745, "longitude": 88.3639, "distance": 211.3 }
]
```

### `GET /api/facilities` · `GET /api/facilities/{facility_id}` · `GET /api/facilities/types`

List with filters and paging; full details; the category and status vocabularies used by
the filter sheet.

### `POST /api/facilities` · `PATCH /api/facilities/{facility_id}` — `AUTHORITY`

Create a facility; update its details or accessibility status. `PATCH` is the
accessibility-status update path and refreshes `last_updated`.

## Reports (shared)

### `GET /api/reports/options`

Issue types, severities and statuses for the reporting screens.

### `GET /api/reports/map`

Query: `latitude`, `longitude`, `radius`, `only_open`, `limit`. Report markers for the
map. Marker data only — no route geometry is ever returned.

### `GET /api/reports/{report_id}/image`

A short-lived link to the evidence image.

```json
{ "url": "https://bucket.s3...X-Amz-Signature=...", "expires_in": 900, "storage": "s3", "external": false }
```

With S3 this is a presigned URL. Without it, the URL carries a scoped media token so an
`<img>` can load it. Reports imported from CSV return their external `image_url`
verbatim with `"external": true`.

Citizens may only access evidence on their own reports; authority and maintenance staff
may access any.

### `GET /api/reports/{report_id}/image/raw`

Streams or redirects to the image. Accepts either the `Authorization` header or a
`?token=` media token scoped to that one report.

## Authority — `AUTHORITY`

### `GET /api/authority/overview`

```json
{
  "total_reports": 26, "new_reports": 15, "under_review": 15, "valid_reports": 10,
  "invalid_reports": 1, "assigned_tasks": 2, "in_progress": 1, "resolved": 3,
  "high_severity_open": 8, "awaiting_verification": 0, "total_facilities": 15,
  "resolution_rate": 11.5
}
```

All counted from the database at request time.

### `POST /api/authority/reports/upload`

`multipart/form-data` with `file`. Max 5 MB, 5000 rows. See [CSV.md](CSV.md).

```json
{ "totalRows": 10, "successfulRows": 9, "failedRows": 1,
  "errors": [ { "row": 7, "reportId": "RS-1007", "reason": "Invalid latitude" } ],
  "inserted": ["RS-1001", "..."] }
```

### `GET /api/authority/reports`

Filters: `issue_type`, `severity`, `validation_status`, `status`, `priority`, `source`,
`location`, `date_from`, `date_to`, `search`, `sort`, `page`, `page_size`.
`search` matches report ID, location, issue type, description and user ID.

### `GET /api/authority/reports/{report_id}` · `GET /api/authority/reports/{report_id}/audit`

Full details; the audit trail for that report.

### `POST /api/authority/reports/{report_id}/validate`

```json
{ "validation_status": "Valid", "note": "Photo clearly shows the blockage." }
```

Records the reviewer and time, moves a `Submitted` report to `Under Review`, and
notifies the reporter.

### `POST /api/authority/reports/{report_id}/status`

Move a report between statuses manually.

### `POST /api/authority/reports/{report_id}/priority/predict`

Runs the model and stores the recommendation. Does **not** set `final_priority`.

```json
{
  "report_id": "RS-1001",
  "predicted_priority": "Critical",
  "confidence": 0.77,
  "model": "xgboost",
  "rationale": ["'Ramp Blocked' fully blocks step-free access", "Citizen-reported severity is High", "Photo evidence attached"],
  "probabilities": { "Low": 0.01, "Medium": 0.06, "High": 0.16, "Critical": 0.77 }
}
```

### `POST /api/authority/reports/{report_id}/priority/confirm`

```json
{ "final_priority": "Critical" }
```

Sets `final_priority` and records who confirmed it. The audit entry flags whether the
human overrode the model.

### `POST /api/authority/reports/{report_id}/assign`

```json
{ "assigned_team": "Team Alpha", "assigned_to": "MN201", "note": "Bollards required." }
```

Creates a task, moves the report to `Assigned` and notifies both the reporter and the
assignee. Returns 409 if an open task already exists, or if the report is `Invalid`.

### `GET /api/authority/tasks` · `POST /api/authority/tasks/{task_id}/verify`

List every task. Verification:

```json
{ "approved": true, "notes": "Site photo confirms the ramp is clear." }
```

Approving marks the task `Verified`, the report `Resolved`, and notifies the reporter.
Rejecting returns it to `In Progress` and clears `completed_at`. Only `Completed` tasks
can be verified.

### `GET /api/authority/teams` · `GET /api/authority/filters` · `GET /api/authority/audit`

Assignable teams and members; filter vocabularies; the audit trail.

### `DELETE /api/authority/reports/{report_id}`

Removes a report imported in error. Refuses (409) if it has maintenance history.

## Analytics — `AUTHORITY`

### `GET /api/analytics?days=30`

Breakdowns by issue type, severity, status, validation, confirmed priority, source and
top locations; a daily submitted/resolved trend; and the average hours from report to
verified repair.

### `GET /api/analytics/map`

Every report as a marker for the authority map.

## Maintenance — `MAINTENANCE`

A maintenance user only ever sees tasks assigned to them personally or unclaimed tasks
belonging to their team.

### `GET /api/maintenance/summary`

Counts by task status for the caller's queue.

### `GET /api/maintenance/tasks` · `GET /api/maintenance/tasks/{task_id}`

The queue and one task, each carrying the underlying report.

### `POST /api/maintenance/tasks/{task_id}/status`

```json
{ "status": "In Progress", "maintenance_notes": "Team dispatched to site." }
```

`Assigned → In Progress → Completed`. Setting `Verified` or `Rejected` returns 403 —
those are authority decisions. `Completed` returns 400 without a resolution photo. The
first responder on an unclaimed team task becomes its assignee.

### `PATCH /api/maintenance/tasks/{task_id}/notes`

Update the notes without changing status.

### `POST /api/maintenance/tasks/{task_id}/resolution`

`multipart/form-data` with `photo` and optional `maintenance_notes`. Uploads to
`resolutions/<year>/<month>/<report id>-fixed.<ext>` in S3 and stores only the key.

### `GET /api/maintenance/tasks/{task_id}/resolution/link`

A short-lived link to the resolution photo, for the assignee or an authority reviewer.

### `GET /api/maintenance/tasks/{task_id}/resolution`

Streams or redirects to the photo. Accepts the header or a scoped `?token=`.

## Notifications — any authenticated role

### `GET /api/notifications`

Query: `unread_only`, `page`, `page_size`.

### `GET /api/notifications/count`

`{ "total": 12, "unread": 3 }`

### `POST /api/notifications/{notification_id}/read` · `POST /api/notifications/read-all`
