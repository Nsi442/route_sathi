# Image storage

Two kinds of image flow through the system:

- **Report evidence** — the photo a citizen attaches when reporting a barrier.
- **Resolution proof** — the photo a maintenance worker uploads after the repair.

Binary images are **never stored in PostgreSQL**. The database holds the object key; S3
holds the bytes.

## Flows

```
Citizen evidence:
  User → React → FastAPI → Amazon S3 → object key → PostgreSQL

Resolution proof:
  Maintenance Portal → FastAPI → Amazon S3 → resolution object key → PostgreSQL

Read:
  PostgreSQL → FastAPI → S3 object key → temporary presigned URL → browser
```

## Choosing a provider

The storage layer speaks the S3 API, and every major object store implements it. So
the same code and the same four environment variables work with any of these — you are
not tied to AWS.

| Provider | Free tier | Egress cost | Setup effort |
| --- | --- | --- | --- |
| **Cloudflare R2** *(recommended)* | 10 GB, 1M writes/month | **None** | Create bucket, create API token. No IAM policy to write. |
| Amazon S3 | 5 GB for 12 months | Charged per GB | Create bucket, create IAM user, attach a policy |
| Supabase Storage | 1 GB | Charged above the tier | Create project, use the S3-compatible keys |
| Backblaze B2 | 10 GB | Free up to 3x storage | Create bucket, create application key |

**Cloudflare R2 is the simplest option** and the one to pick if you have no existing
AWS setup: signing up takes a couple of minutes, there is no IAM policy JSON to get
right, and egress is free — which matters here, because every evidence photo a reviewer
opens is egress.

## Environment

```
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=auto                # 'auto' for R2; a real region for AWS
S3_BUCKET=routesathi-media
S3_ENDPOINT_URL=              # empty for Amazon S3; the provider URL otherwise
S3_PRESIGN_EXPIRY=900
MAX_UPLOAD_BYTES=8388608
```

Storage is active only when `S3_BUCKET`, `AWS_ACCESS_KEY_ID` and
`AWS_SECRET_ACCESS_KEY` are all set. `GET /api/health` names the provider it detected —
`s3`, `cloudflare-r2`, `supabase-storage`, `backblaze-b2` or `database-fallback`.

### Cloudflare R2 in five steps

1. Cloudflare dashboard → **R2** → **Create bucket** → name it `routesathi-media`.
   Leave public access off.
2. **R2 → Manage R2 API Tokens → Create API Token**, with *Object Read & Write*
   permission on that bucket.
3. Copy the Access Key ID and Secret Access Key it shows you once.
4. Copy the **S3 API** endpoint from the bucket settings — it looks like
   `https://<account-id>.r2.cloudflarestorage.com`.
5. Set the five variables in Render:

```
AWS_ACCESS_KEY_ID=<access key id>
AWS_SECRET_ACCESS_KEY=<secret access key>
AWS_REGION=auto
S3_BUCKET=routesathi-media
S3_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
```

Nothing else changes. Uploads, presigned URLs and the private-by-default posture all
behave the same, because R2 implements the same API.

Two AWS-only request options — per-object ACLs and the `ServerSideEncryption` header —
are sent only when `S3_ENDPOINT_URL` is empty, since R2 rejects them. R2 buckets are
private by default and encrypted at rest regardless.

## Object keys

```
reports/2026/08/RS-1001-a1b2c3d4.jpg
resolutions/2026/08/RS-1001-fixed-e5f6a7b8.jpg
```

Year and month partition the bucket; the short random suffix means re-uploading an image
for the same report never silently overwrites the previous one, so the evidence history
survives.

## Bucket setup

Keep **Block all public access** switched on. Nothing is served directly from the
bucket — every read goes through a presigned URL minted by the API after it has checked
the caller's role and ownership.

```bash
aws s3api create-bucket \
  --bucket routesathi-media \
  --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1

aws s3api put-public-access-block \
  --bucket routesathi-media \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

aws s3api put-bucket-encryption \
  --bucket routesathi-media \
  --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
```

Objects are additionally written with `ServerSideEncryption=AES256` and a private ACL.

### CORS

Only needed if you serve presigned URLs to a browser on a different origin. Restrict it
to your deployed domains:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET"],
    "AllowedOrigins": ["https://your-app.vercel.app"],
    "ExposeHeaders": [],
    "MaxAgeSeconds": 3000
  }
]
```

### Minimal IAM policy

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::routesathi-media/*"
    }
  ]
}
```

No `s3:ListBucket` is required — the application always addresses objects by exact key.

### Lifecycle

Evidence photos are civic records; keep them for as long as your retention policy
requires. A reasonable default is to transition `reports/` and `resolutions/` prefixes to
Infrequent Access after 90 days.

## Upload validation

Enforced in `backend/services/storage.py` before anything reaches S3:

- Content types: `image/jpeg`, `image/png`, `image/webp`, `image/heic`, `image/heif`.
- Size: `MAX_UPLOAD_BYTES`, default 8 MB.
- Empty files are rejected.

Uploads are read and forwarded within the request. Nothing is written to a local
filesystem, which is what makes the flow safe on a serverless runtime.

## Reading images securely

The bucket is private, so a URL is minted per request:

1. The client calls `GET /api/reports/{id}/image` (or
   `/api/maintenance/tasks/{id}/resolution/link`) **with** its bearer token.
2. The API checks the caller's role and ownership.
3. It returns a presigned `GET` URL valid for `S3_PRESIGN_EXPIRY` seconds.
4. The browser loads that URL directly from S3.

A browser cannot attach an `Authorization` header to an `<img src>` or a download link,
which is why the link is fetched separately rather than pointing the tag at a protected
endpoint.

### Development fallback

Without storage credentials the same endpoints work, but bytes are held in the
`stored_files` table and the link endpoints return a URL carrying a **short-lived,
single-resource media token** instead of a presigned URL. The token is scoped to exactly
one report or task and expires in 15 minutes.

This exists so a fresh clone runs end to end with no cloud account. It is not a
production storage strategy: `GET /api/health` reports
`"object_storage": "database-fallback"` whenever it is in effect.

## CSV imports do not touch S3

Reports imported from CSV carry an external `image_url`, stored verbatim as TEXT. No
S3 upload and no image processing happen during import. The link endpoint returns that
URL with `"external": true` so the UI knows it is a third-party resource.
