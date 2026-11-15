# 🐔 PoultryTrack — Poultry Integration Tracking Software

![CI](https://github.com/saicharanreddyjillella-collab/Poultry-Tracker/actions/workflows/ci.yml/badge.svg)

A full-stack web application for tracking daily mortality, feed consumption, and flock performance across multiple poultry farms.

**Stack:** React (Vite) + Django REST Framework + SQLite

---

## Quick Start (Mac)

### 1. Start the Django Backend

Open a terminal:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install django djangorestframework django-cors-headers
python3 manage.py migrate
python3 manage.py createsuperuser   # optional: create admin login
python3 manage.py runserver
```

Backend will run at **http://localhost:8000**
Admin panel at **http://localhost:8000/admin/**

### 2. Start the React Frontend

Open a SECOND terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend will run at **http://localhost:5173**

### 3. Open your browser

Go to **http://localhost:5173** — you're ready!

---

## What You Can Do

1. **Add Farms** — name, owner, location, house count
2. **Place Flocks** — breed, placement date, number of chicks
3. **Enter Daily Data** — mortality, feed, water, body weight, notes
4. **View Cumulative Charts** — mortality trend, feed trend, weight curve
5. **Dashboard** — see all farms and live flock stats at a glance

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/dashboard/ | GET | Overview stats |
| /api/farms/ | GET, POST | List / create farms |
| /api/farms/:id/ | GET, PUT, DELETE | Farm detail |
| /api/flocks/ | GET, POST | List / create flocks |
| /api/flocks/:id/ | GET, PUT | Flock detail |
| /api/flocks/:id/cumulative/ | GET | Day-by-day cumulative data |
| /api/daily-entries/ | GET, POST | Daily entries (filter: ?flock=id) |
| /api/medications/ | GET, POST | Medications (filter: ?flock=id) |

---

## Folder Structure

```
poultry-tracker/
├── backend/
│   ├── config/          # Django project settings
│   ├── core/            # Main app (models, views, serializers)
│   ├── db.sqlite3       # Database (auto-created)
│   ├── manage.py
│   └── venv/            # Python virtual environment
├── frontend/
│   ├── src/
│   │   ├── api/         # API client (axios)
│   │   ├── pages/       # Dashboard, FarmForm, FarmDetail, FlockDetail
│   │   ├── App.jsx      # Main app with routing
│   │   └── App.css      # All styles
│   └── package.json
└── README.md
```

---

## White-Label Branding

Every customer-facing name, logo, address and colour is driven by
`frontend/src/config/brand.js`, sourced from build-time environment
variables. To rebrand the product for another company:

1. `cd frontend && cp .env.example .env`
2. Edit `.env` — set `VITE_BRAND_COMPANY`, `VITE_BRAND_FEEDS_NAME`,
   `VITE_BRAND_ADDRESS`, `VITE_BRAND_PRIMARY_COLOR`, etc.
3. `npm run build`

The built image carries that company's branding throughout (nav, login,
setup, landing, dashboards, bill/invoice header, browser tab). `.env` is
git-ignored, so each customer's branding stays out of the repo — commit only
`.env.example`. Leaving any key blank falls back to the default in
`brand.js`.

---

## Production Security (settings)

Settings are safe-by-default: `DEBUG` defaults to **False**, and when `DEBUG`
is off a `SECRET_KEY` **must** be supplied via the environment (the app refuses
to start otherwise). Configure via environment variables (see
`backend/.env.example`):

- `SECRET_KEY` — required in production. Generate with
  `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`
- `DEBUG=True` — for local development only.
- `ALLOWED_HOSTS` — comma-separated hostnames (default `localhost,127.0.0.1`).
- `CORS_ALLOWED_ORIGINS` — comma-separated front-end origins allowed to call the API.
- `DISABLE_HTTPS=True` — only for a deliberate non-HTTPS internal deploy.

With `DEBUG=False` the app also enables secure cookies, SSL redirect, HSTS and
related headers (unless `DISABLE_HTTPS=True`). `docker-compose.yml` already
passes these through from your deploy `.env`.

---

## Continuous Integration

Every push and pull request to `main` or `release/feeds-only` runs
`.github/workflows/ci.yml`: Django system check, migration-sync check, and the
full pytest suite against **PostgreSQL 16** (matching production), plus the
Vite frontend build. Keep CI green before merging or building an image.

## Backups & Restore

Daily automated backups of the database **and** uploaded documents (02:30 IST),
verified on creation and restore-tested weekly into a throw-away database.
Install on the server with `bash deploy/install-backups.sh` (done automatically by
`deploy/setup.sh`), then add an off-box rclone destination and a healthchecks.io
alert URL in `/etc/poultrytrack/backup.env`. Restore with
`bash deploy/restore.sh latest`. Full runbook: [docs/BACKUPS.md](docs/BACKUPS.md).

## Run the production build locally (Mac)

Same images as the server (DEBUG=False, Postgres 16, gunicorn, nginx), plain
http on **http://localhost:8080**. Needs Docker Desktop running.

```bash
git checkout release/feeds-only     # or main
bash deploy/local.sh up             # build + start; first run creates .env.local
bash deploy/local.sh status         # containers + health
bash deploy/local.sh logs           # follow backend logs
bash deploy/local.sh down           # stop (data kept)
bash deploy/local.sh reset          # stop and wipe the local database/uploads
```

A fresh database opens the first-time Setup page to create the admin. To try a
copy of the server's data, copy a backup file over and run
`BACKUP_DIR=<folder> bash deploy/restore.sh <file.sql.gz>`.
