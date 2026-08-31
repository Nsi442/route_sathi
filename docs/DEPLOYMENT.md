# Deployment — Render (API) + Vercel (frontend)

```
GitHub Repository
        │
        ├──────────────▶ Vercel ──── React frontend (static build in dist/)
        │                   │
        │                   │  /api/*  proxied server-side
        │                   ▼
        └──────────────▶ Render ──── FastAPI + XGBoost (uvicorn)
                            │
                   ┌────────┴────────┐
                   ▼                 ▼
              Neon PostgreSQL     Amazon S3
                 + PostGIS          Images
```

## Why the API is not a Vercel function

The ML stack does not fit in a serverless function:

| Package | Installed size |
| --- | --- |
| NVIDIA CUDA libraries (pulled in by xgboost on Linux) | 454 MB |
| xgboost | 228 MB |
| scipy | 143 MB |
| numpy | 73 MB |
| scikit-learn | 50 MB |
| **ML stack total** | **~948 MB** |
| Everything else the API needs | 98 MB |

A Vercel Python function is capped at roughly 250 MB unzipped, so the ML stack
cannot ship there. Render has no such cap, which is why the API runs there and
keeps real XGBoost inference in production.

If you would rather have a single Vercel project, remove `xgboost`,
`scikit-learn` and `numpy` from `requirements.txt` and deploy the API as a
Vercel function: the code falls back to the deterministic rule engine
automatically, with no code change. Measured over 3000 generated reports the
rule engine picks the identical priority band 89.7% of the time and is never
more than one band away, because it is the same scoring function that labelled
the model's training data. See [ML.md](ML.md).

## Order of operations

Render first (you need its URL for Vercel), then Vercel.

---

## 1. Neon — the database

1. Create a project at [neon.com](https://neon.com).
2. Copy the **pooled** connection string (it has `-pooler` in the host).
3. Keep it handy; it goes into Render as `DATABASE_URL`.

PostGIS is installed automatically on first boot — the app runs
`CREATE EXTENSION IF NOT EXISTS postgis` and sets up the geography columns,
GiST indexes and triggers. Nothing to do by hand.

## 2. Amazon S3 — evidence images

Follow [STORAGE.md](STORAGE.md) to create a private bucket and an IAM user limited to
`PutObject` / `GetObject` / `DeleteObject` on that bucket. Note the access key,
secret key, region and bucket name.

Skipping this is fine for a first deploy — the API falls back to storing images
in the database and tells you so at `/api/health`.

## 3. Render — the API

**Render Dashboard → New → Blueprint → select this repository.** Render reads
[`render.yaml`](../render.yaml), which already sets the build command, start
command, health check path and Python version.

Then set the secret variables it prompts for (they are marked `sync: false` in
the blueprint precisely so they are never stored in the repository):

| Variable | Value |
| --- | --- |
| `DATABASE_URL` | Neon pooled connection string |
| `JWT_SECRET` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `AWS_ACCESS_KEY_ID` | From step 2 |
| `AWS_SECRET_ACCESS_KEY` | From step 2 |
| `AWS_REGION` | e.g. `ap-south-1` |
| `S3_BUCKET` | Your bucket name |
| `CORS_ORIGINS` | Your Vercel domain, e.g. `https://routesathi.vercel.app` |

Deploy, then check:

```bash
curl https://YOUR-SERVICE.onrender.com/api/health
```

Expect `"database": "postgresql"`, `"spatial_backend": "postgis"`,
`"object_storage": "s3"` and `"ml_backend": "xgboost"`. Anything else means a
variable is missing or wrong.

**Copy the service hostname** — you need it in the next step.

### Free tier caveats

- **The service sleeps after 15 minutes of inactivity.** The next request wakes
  it and takes 30–60 seconds. Fine for coursework; upgrade to the paid instance
  (about $7/month) before demoing live to an audience.
- **512 MB RAM.** The ML stack uses roughly 200–300 MB resident once loaded, so
  it fits, but not with much room. If the service is OOM-killed, set
  `ML_ENABLED=0` — the API then serves priority from the rule engine and the
  memory footprint drops sharply.
- The first priority prediction after a cold start trains and caches the model,
  so it takes a second or two longer than later ones.

## 4. Vercel — the frontend

1. **Edit [`vercel.json`](../vercel.json)** and replace
   `routesathi-api.onrender.com` with your Render hostname, in both rewrites.
   Commit and push. This is the only place the API hostname appears.
2. Import the repository at [vercel.com/new](https://vercel.com/new). The Vite
   preset is detected; `vercel.json` supplies the rest.
3. Deploy.

**No environment variables are needed on Vercel.** The frontend has no secrets
in it — it only ever calls same-origin `/api/...` paths.

### How the proxy works

```json
{ "source": "/api/:path*", "destination": "https://YOUR-SERVICE.onrender.com/api/:path*" }
```

Vercel forwards `/api/*` to Render server-side, so:

- the browser only ever sees one origin, and never makes a cross-origin request
- there is no CORS preflight on any API call
- no API hostname is compiled into the JavaScript bundle
- the frontend code is byte-identical between local development and production

[`.vercelignore`](../.vercelignore) excludes `api/`, `backend/` and
`requirements.txt` so Vercel does not try to build a Python function.

## 5. Seed the first accounts

Authority and maintenance accounts cannot be self-registered, so seed them once
against the live database from your own machine:

```bash
DATABASE_URL='postgresql+psycopg://...pooler...' python scripts/seed_data.py
```

**Change the seeded passwords immediately afterwards** — they are published in
this repository.

## 6. Verify end to end

1. Open your Vercel URL, sign in as the citizen account.
2. Allow location access; the home screen counts should be non-zero.
3. Submit a report with a photo.
4. Sign in as the authority account, validate it, request a priority
   recommendation (confirms XGBoost is live), and assign it.
5. Sign in as the maintenance account, upload a resolution photo, submit.
6. Back as the authority, verify it. The report should close as `Resolved`.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Frontend loads, every API call 404s | `vercel.json` still points at the placeholder hostname |
| First request takes ~45 s | Render free tier waking from sleep. Expected. |
| `"database": "unavailable"` | `DATABASE_URL` wrong, or missing `sslmode=require` |
| `"spatial_backend": "haversine"` on Neon | PostGIS could not be created; check the role's privileges. The app still works. |
| `"object_storage": "database-fallback"` | An S3 variable is missing |
| `"ml_backend": "rules"` | `ML_ENABLED=0`, or xgboost failed to import — check the Render build log |
| 401 on every request after a redeploy | `JWT_SECRET` changed, invalidating issued tokens. Sign in again. |
| Render build times out | The ML wheels are large; the first build takes several minutes |

## Local development is unchanged

```bash
npm run api    # uvicorn on :8000
npm run dev    # Vite on :5173, proxies /api to :8000
```

The Vite dev proxy plays the same role locally that the Vercel rewrite plays in
production, so the frontend uses the same relative paths in both.
