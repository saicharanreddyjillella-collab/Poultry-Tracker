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
