# 🐔 PoultryTrack — Poultry Integration Tracking Software

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
