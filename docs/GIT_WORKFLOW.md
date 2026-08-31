# Git workflow

## Branches

| Branch | Purpose |
| --- | --- |
| `main` | Production. Every commit is deployable. Protected. |
| `develop` | Integration branch for the next release. |
| `feature/*` | One branch per unit of work, cut from `develop`. |
| `hotfix/*` | Urgent production fix, cut from `main`. |

Feature branches used on this project:

```
feature/user-portal      feature/map          feature/reporting
feature/authority        feature/maintenance  feature/xgboost
feature/database         feature/cloud
```

## Day-to-day

```bash
git checkout develop
git pull origin develop

git checkout -b feature/map
# ... work ...
git add -A
git commit -m "Add facility filtering to the accessibility map"
git push -u origin feature/map
```

Open a pull request into `develop`. Once it is reviewed and CI is green, squash-merge and
delete the branch.

## Releasing

```bash
git checkout main && git pull origin main
git merge --no-ff develop
git tag -a v1.0.0 -m "RouteSathi MVP"
git push origin main --tags
```

Vercel deploys `main` to production and every other branch to a preview URL.

## Hotfixes

```bash
git checkout -b hotfix/csv-timestamp-parsing main
# ... fix, commit ...
git push -u origin hotfix/csv-timestamp-parsing
```

Merge into `main`, then into `develop`, so the fix is not lost in the next release.

## Commit messages

Write what changed and why, in the imperative:

```
Add PostGIS radius search to facility discovery

Nearby search used a bounding box, which returned corner results outside
the requested radius. Use ST_DWithin against the geography column and
ST_Distance for the metre value, both served by the new GiST index.
```

Keep the subject under ~72 characters. Reference issues with `Fixes #123`.

## Never commit

- `.env` or any real environment file
- AWS access keys or secret keys
- `JWT_SECRET`
- The Neon password or a full `DATABASE_URL`
- Private keys, certificates, `credentials` files
- Local databases (`*.db`, and SQLite's `-wal` / `-shm` companions)
- `node_modules/`, `dist/`, `.venv/`

`.gitignore` covers all of these. Every variable is documented with a placeholder in
`.env.example` — add new variables there, never their real values.

If a secret is committed, rotate it first and rewrite history second. Rotation is what
actually protects you; the credential is compromised the moment it is pushed.

## Pull requests

A PR should state what changed, why, and how it was verified. Before requesting review:

```bash
npm run build       # the frontend compiles
pytest -q           # the API suite passes
```

Keep PRs focused — one concern per branch. A PR that touches the CSV importer, the map
and the auth flow is three PRs.

## Repository hygiene

- `README.md` and `docs/` are part of the change, not an afterthought: if a PR changes
  the API, the environment variables or the schema, it updates the docs in the same PR.
- `.env.example` stays in sync with `backend/core/config.py`.
- New endpoints get a test in `tests/test_api.py`.
