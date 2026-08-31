# CSV report import

Bulk import lives on the **authority dashboard** — the first page of the portal — not on
the reports page.

```
Authority → CSV selected → React → Axios
  → POST /api/authority/reports/upload
  → FastAPI → CSV parser → validation → PostgreSQL
  → response → dashboard refresh
```

## Format

```
report_id,user_id,issue_type,location,latitude,longitude,severity,description,image_url,timestamp,validation_status,status,source
```

```
RS-1001,U1042,Blocked Ramp,"College Street, Kolkata",22.5726,88.3639,High,"Wheelchair ramp blocked by parked vehicle.","https://example.com/RS-1001.jpg",2026-08-31T10:30:00+05:30,Needs Review,Submitted,Community
RS-1002,U1043,Damaged Footpath,"Park Street, Kolkata",22.5535,88.3529,Medium,"Uneven footpath surface makes wheelchair movement difficult.","https://example.com/RS-1002.jpg",2026-08-30T15:20:00+05:30,Needs Review,Submitted,Community
RS-1003,U1044,Waterlogging,"Salt Lake, Kolkata",22.5726,88.4331,High,"Waterlogging blocks the accessible pathway.","https://example.com/RS-1003.jpg",2026-08-29T17:10:00+05:30,Needs Review,Submitted,Community
```

**There is no priority column.** Priority is recommended by the model afterwards and
confirmed by a human; it is never imported.

Working fixtures: [`data/sample_reports.csv`](../data/sample_reports.csv) (all valid)
and [`data/sample_reports_with_errors.csv`](../data/sample_reports_with_errors.csv)
(exercises every rejection reason).

## Validation

| Column | Required | Rule |
| --- | --- | --- |
| `report_id` | yes | Unique within the file **and** against the database |
| `user_id` | yes | Non-empty |
| `issue_type` | yes | Canonical type, or a recognised alias |
| `latitude` | yes | Numeric, −90 to 90 |
| `longitude` | yes | Numeric, −180 to 180 |
| `severity` | yes | `Low`, `Medium`, `High` |
| `description` | yes | Non-empty |
| `timestamp` | yes | Parseable date/time |
| `validation_status` | yes | `Needs Review`, `Valid`, `Invalid` |
| `status` | yes | `Submitted`, `Under Review`, `Assigned`, `In Progress`, `Resolved` |
| `source` | yes | Non-empty |
| `location` | no | Stored as `location_text` |
| `image_url` | no | Stored verbatim as TEXT |

Comparisons are case-insensitive; header names tolerate spaces, hyphens and underscores.

### Canonical issue types

`Ramp Blocked`, `Footpath Damaged`, `No Accessible Entrance`, `Stairs / No Ramp`,
`Waterlogging`, `Blocked Crossing`, `Other`.

Aliases commonly found in municipal exports are mapped automatically — for example
`Blocked Ramp` → `Ramp Blocked`, `Damaged Footpath` → `Footpath Damaged`, `Flooding` →
`Waterlogging`, `No Ramp` → `Stairs / No Ramp`.

### Timestamps

ISO-8601 with an offset is preferred (`2026-08-31T10:30:00+05:30`). Also accepted:
`YYYY-MM-DD HH:MM:SS`, `YYYY-MM-DD`, `DD/MM/YYYY HH:MM`, `DD-MM-YYYY`. Values without an
offset are interpreted as IST and stored as UTC.

## Response

Valid rows are committed; invalid rows are reported individually. Row numbers count the
header as row 1, so they line up with what a spreadsheet shows.

```json
{
  "totalRows": 10,
  "successfulRows": 9,
  "failedRows": 1,
  "errors": [
    { "row": 7, "reportId": "RS-1007", "reason": "Invalid latitude" }
  ],
  "inserted": ["RS-1001", "RS-1002", "..."]
}
```

Rejection reasons you will see:

| Reason | Cause |
| --- | --- |
| `Invalid latitude` / `Invalid longitude` | Not numeric, or out of range |
| `severity must be one of Low, Medium, High` | Unrecognised severity |
| `Unknown issue_type 'X'` | Not a canonical type or known alias |
| `Invalid or missing timestamp` | Unparseable |
| `validation_status must be one of ...` | Unrecognised value |
| `status must be one of ...` | Unrecognised value |
| `Duplicate report_id within the file` | The same ID appears twice in the upload |
| `Duplicate report_id (already imported)` | The ID already exists in the database |
| `Missing description` / `Missing user_id` / `Missing source` | Required field is blank |

A malformed file — no header, missing required columns, undecodable bytes — is rejected
whole with `400` and a message naming the missing columns.

## What import does not do

- No S3 upload; `image_url` is stored as text.
- No image download or processing.
- No ML inference; `predicted_priority` and `final_priority` stay null.
- No notifications; imported reports have no in-app reporter to notify.

Every import writes an audit entry recording the filename and the row counts.

## Limits

5 MB per file, 5000 rows per import. Blank lines are skipped and do not count towards
`totalRows`.
