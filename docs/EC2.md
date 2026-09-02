# Deploying on a single AWS EC2 instance

Everything on one server: nginx serves the built React app and reverse-proxies
`/api` to the FastAPI process; PostgreSQL with PostGIS runs alongside it; S3
holds the photos.

```
                    ┌──────────────────────────────────────┐
   Browser ──:80──▶ │  EC2 instance (Ubuntu 24.04)         │
                    │                                      │
                    │   nginx                              │
                    │     ├─ /            → dist/ (React)  │
                    │     └─ /api/*       → 127.0.0.1:8000 │
                    │                          │           │
                    │                     gunicorn         │
                    │                    + uvicorn workers │
                    │                          │           │
                    │                     FastAPI + XGBoost│
                    │                          │           │
                    │   PostgreSQL 16 + PostGIS ◀──────────┤
                    └──────────────────────────┬───────────┘
                                               │
                                        Amazon S3 (photos)
```

The browser only ever sees one origin, so there is no CORS anywhere and no API
hostname is compiled into the frontend bundle.

## What you need before starting

| | |
| --- | --- |
| An AWS account | Free tier is enough to try it |
| An EC2 key pair | To SSH in |
| A domain name | **Optional.** Only needed for HTTPS |

## 1. Launch the instance

| Setting | Value |
| --- | --- |
| AMI | **Ubuntu Server 24.04 LTS** |
| Instance type | **t3.small** (2 GB RAM) — see the note below |
| Storage | 20 GB gp3 |
| Key pair | Yours |

**On instance size.** `t2.micro` is the free-tier option but has 1 GB of RAM,
and it has to hold PostgreSQL, nginx and an ML stack that needs roughly
200–300 MB resident. It will build and boot, but it is tight and the npm build
step may run out of memory. Two ways through:

- Use `t3.small` (about $15/month in ap-south-1), or
- Stay on `t2.micro`, add swap, and set `ML_ENABLED=0` so priority comes from
  the rule engine instead of XGBoost:

  ```bash
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
  ```

### Security group

| Type | Port | Source | Why |
| --- | --- | --- | --- |
| SSH | 22 | **Your IP only** | Administration |
| HTTP | 80 | 0.0.0.0/0 | The site |
| HTTPS | 443 | 0.0.0.0/0 | Only if you add TLS |

Do **not** open 5432 or 8000. PostgreSQL and gunicorn both listen on localhost
only, and nothing outside the instance should reach them.

## 2. Give the instance an IAM role for S3

This is the part worth doing properly. Instead of putting AWS keys in a file on
the server, attach a role and let the instance fetch temporary credentials
itself.

1. **IAM → Roles → Create role** → *AWS service* → *EC2*.
2. Attach a policy with only what the app needs:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
    "Resource": "arn:aws:s3:::routesathi-media/*"
  }]
}
```

3. Name it `routesathi-ec2`, then **EC2 → your instance → Actions → Security →
   Modify IAM role** and attach it.
4. Create the bucket (`routesathi-media`), keeping **Block all public access
   on**. Nothing is ever served straight from it — the API mints a presigned
   URL after checking the caller's role.

With the role attached, the server config is just:

```
S3_BUCKET=routesathi-media
AWS_REGION=ap-south-1
AWS_USE_INSTANCE_ROLE=1
```

No access key, no secret key, nothing long-lived on disk. AWS rotates the
credentials automatically, and revoking access is one IAM change.

*If you would rather use keys*, set `AWS_USE_INSTANCE_ROLE=0` and provide
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`. `S3_ENDPOINT_URL` also still
works, so Cloudflare R2 is an option here too.

## 3. Run the setup script

SSH in and run it. It installs everything, builds the frontend, creates the
database and starts the services.

```bash
ssh -i your-key.pem ubuntu@<instance-public-ip>

sudo apt-get update && sudo apt-get install -y git
sudo git clone https://github.com/Nsi442/route_sathi.git /opt/routesathi
sudo bash /opt/routesathi/deploy/setup-ec2.sh
```

It is **idempotent** — safe to re-run, which is also how you deploy updates.

What it does:

1. Installs PostgreSQL 16 + PostGIS, Python, Node 20 and nginx.
2. Creates the `routesathi` service account.
3. Creates the database, role and PostGIS extension.
4. Clones the repo to `/opt/routesathi` and installs dependencies.
5. Builds the frontend into `dist/`.
6. Writes `/etc/routesathi/routesathi.env` with a **generated** JWT secret and
   database password, `chmod 600`, owned by root.
7. Installs and starts the systemd unit and the nginx site.
8. Checks `/api/health` and prints the result.

## 4. Add your S3 bucket

The script cannot know your bucket name, so set it once:

```bash
sudo nano /etc/routesathi/routesathi.env
```

```
S3_BUCKET=routesathi-media
AWS_REGION=ap-south-1
AWS_USE_INSTANCE_ROLE=1
```

```bash
sudo systemctl restart routesathi-api
```

Skipping this is fine to start with — the API stores photos in the database
instead and says so at `/api/health`. That is a development fallback, not a
production answer.

## 5. Create the staff accounts

Authority and maintenance accounts cannot be self-registered:

```bash
sudo bash /opt/routesathi/deploy/seed.sh
```

**Then change every seeded password.** They are `Password123!` and published in
this repository, so anyone who reads it can sign in as your authority account.

## 6. Check it

```bash
curl http://<instance-public-ip>/api/health
```

| Field | You want | If not |
| --- | --- | --- |
| `database` | `postgresql` | Check `DATABASE_URL` and `systemctl status postgresql` |
| `spatial_backend` | `postgis` | The extension did not install. The app still works. |
| `object_storage` | `s3-instance-role` | `database-fallback` → `S3_BUCKET` is unset |
| `ml_backend` | `xgboost` | `rules` → `ML_ENABLED=0`, or xgboost failed to install |

Then open `http://<ip>/` and walk the product once: report with a photo →
validate → priority → assign → resolve → verify. That touches every service in
one pass.

## 7. HTTPS (needs a domain)

Geolocation only works over HTTPS or localhost, so **the citizen app's "find
places near me" will not work over plain HTTP on a public IP.** If you want the
location features to work for real users, you need TLS, and TLS needs a domain.

```bash
# Point an A record at the instance IP first, then:
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d routesathi.example.com
```

Certbot edits the nginx site in place and sets up renewal. Afterwards, tighten
the host allowlist:

```
TRUSTED_HOSTS=routesathi.example.com
```

```bash
sudo systemctl restart routesathi-api
```

## Operating it

```bash
# Logs
sudo journalctl -u routesathi-api -f
sudo tail -f /var/log/nginx/routesathi.error.log

# Restart / status
sudo systemctl restart routesathi-api
sudo systemctl status routesathi-api

# Deploy an update — the script is idempotent
sudo bash /opt/routesathi/deploy/setup-ec2.sh

# Back up the database
sudo -u postgres pg_dump routesathi | gzip > ~/routesathi-$(date +%F).sql.gz
```

### Without nginx

The API can serve the frontend itself, which is useful for a quick test or a
box where you would rather not run a web server:

```
SERVE_FRONTEND=1
```

Then gunicorn answers both the API and the SPA on one port. nginx is still the
better front door in production — it handles TLS, compression and static
caching far better — but the option is there and is covered by tests.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| 502 from nginx | The API is not running. `sudo journalctl -u routesathi-api -n 60` |
| API will not start | Usually a bad `DATABASE_URL`. Check the journal. |
| Blank page, assets 404 | `npm run build` did not complete — often out of memory on `t2.micro`. Add swap. |
| "Location unavailable" in the app | Browsers only give geolocation over HTTPS. See step 7. |
| `spatial_backend: haversine` | PostGIS is missing. `sudo -u postgres psql -d routesathi -c "CREATE EXTENSION postgis;"` |
| Photos upload but do not display | The IAM role is missing `s3:GetObject`, or the bucket name is wrong. |
| Slow first priority prediction | Expected — the model trains and caches on first use. |
| Build killed during npm | Out of memory. Add swap, as above. |

## What this costs

| | Monthly, ap-south-1 |
| --- | --- |
| t3.small, on demand | ~$15 |
| t2.micro | Free for 12 months, then ~$8 |
| 20 GB gp3 | ~$1.60 |
| S3, a few GB | Under $1 |
| Elastic IP | Free while attached to a running instance |

Stopping the instance stops compute charges; storage still bills.
