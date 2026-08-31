# Vercel deployment

One GitHub repository, one Vercel project. The React SPA and the FastAPI API are served
from the same domain, so the frontend only ever uses relative `/api/...` paths.

```
GitHub Repository
        ↓
      Vercel
        │
        ├── React Frontend  (static build in dist/)
        │
        └── FastAPI API     (api/index.py, Python serverless function)
                 │
        ┌────────┴────────┐
        ▼                 ▼
   Neon PostgreSQL     Amazon S3
      + PostGIS          Images
```

## How the routing works

`vercel.json`:

```json
{
  "framework": "vite",
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "functions": { "api/index.py": { "memory": 1024, "maxDuration": 30 } },
  "rewrites": [
    { "source": "/api", "destination": "/api/index" },
    { "source": "/api/(.*)", "destination": "/api/index" },
    { "source": "/((?!api/).*)", "destination": "/index.html" }
  ]
}
```

- `/api/*` → the Python function, which exposes the single FastAPI `app`.
- Everything else → `index.html`, so client-side routes (`/`, `/map`, `/reports`,
  `/authority`, `/maintenance`) survive a hard refresh. The negative lookahead keeps
  the fallback from swallowing API paths, and Vercel checks the filesystem before
  applying rewrites, so real build assets are still served directly.

The Python runtime is inferred from `requirements.txt` and the `.py` file in `api/`;
pinning a runtime version here is unnecessary and a stale pin breaks the build.

`api/index.py` is deliberately the **only** Python file in `api/`. Vercel treats every
`.py` file there as a separate function; keeping one entrypoint that imports from
`backend/` gives one function, one cold start and one connection pool.

```python
# api/index.py
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.main import app

handler = app
```

## Steps

1. Push the repository to GitHub.
2. Import it at [vercel.com/new](https://vercel.com/new). The Vite framework preset is
   detected; `vercel.json` supplies the rest.
3. Add environment variables (**Settings → Environment Variables**), for Production and
   Preview:

   | Variable | Required | Notes |
   | --- | --- | --- |
   | `DATABASE_URL` | yes | Neon **pooled** connection string |
   | `JWT_SECRET` | yes | Long random string; see below |
   | `AWS_ACCESS_KEY_ID` | for images | |
   | `AWS_SECRET_ACCESS_KEY` | for images | |
   | `AWS_REGION` | for images | e.g. `ap-south-1` |
   | `S3_BUCKET` | for images | |
   | `S3_PRESIGN_EXPIRY` | no | seconds, default 900 |
   | `APP_ENV` | no | `production` |
   | `ML_ENABLED` | no | `0` disables the model and uses the rule engine |
   | `ML_MODEL_DIR` | no | must be under `/tmp` — that is the only writable path |
   | `CORS_ORIGINS` | no | Only needed if a different origin calls the API |

   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

4. Deploy. On the first request the API bootstraps the schema and PostGIS objects.
5. Verify:

   ```bash
   curl https://your-app.vercel.app/api/health
   ```

   Confirm `"database": "postgresql"`, `"spatial_backend": "postgis"` and
   `"object_storage": "s3"`. Anything else means an environment variable is missing.

6. Seed an initial authority account. Run the seeder locally against the same
   `DATABASE_URL`:

   ```bash
   DATABASE_URL='postgresql+psycopg://...' python scripts/seed_data.py
   ```

   Change the seeded passwords before going live.

## Serverless constraints the code respects

The FastAPI app is built for a runtime that freezes between invocations:

- **No background workers or schedulers.** Every unit of work completes inside a
  request.
- **No local persistent filesystem.** Uploads are read into memory and forwarded to S3
  within the request; only `/tmp` is writable, and it is used solely as a model cache.
- **No long-lived connections.** The engine keeps a tiny recycled pool
  (`pool_size=1`, `pool_recycle=280`, `pool_pre_ping=True`) and Neon's pooled endpoint
  absorbs the connection churn.
- **Idempotent, cached bootstrap.** Schema setup is guarded by a module-level flag, so a
  warm container pays for it once.
- **Model caching.** The trained booster is written to `ML_MODEL_DIR` and reloaded on
  warm starts; if the path is unwritable the model is retrained in memory rather than
  failing.

## Cold starts

The first request after an idle period pays for the Python runtime, the imports
(XGBoost and pandas are not small) and, once, model training. Subsequent requests are
warm. If cold starts matter more than model quality, set `ML_ENABLED=0` — the rule
engine is instant and needs no numeric stack at request time.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `/api/health` shows `"database": "unavailable"` | `DATABASE_URL` missing or wrong; check `sslmode=require` |
| `"spatial_backend": "haversine"` on Neon | PostGIS could not be created; check the role's privileges. The app still works. |
| `"object_storage": "database-fallback"` | One of `S3_BUCKET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` is missing |
| 401 on every request after a redeploy | `JWT_SECRET` changed, invalidating issued tokens. Sign in again. |
| Function timeout on the first CSV import | Cold start plus a large file; raise `maxDuration` or split the file |
| SPA routes 404 on refresh | `outputDirectory` is not `dist`, or the framework preset was overridden |

## Local production preview

```bash
npm run build
npm run api          # terminal 1
npx vite preview     # terminal 2 — serves dist/
```

Or use the Vercel CLI to reproduce the real routing:

```bash
npm i -g vercel
vercel dev
```
