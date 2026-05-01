# AlmaTour — Async FastAPI + PostgreSQL/Neon Backend

Production-ready rewrite of the AlmaTour backend.  
SQLite + synchronous SQLAlchemy → **async SQLAlchemy 2.0 + asyncpg + Neon Serverless Postgres**.

---

## Project Structure

```
almatour-pg/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI app, all routes, middleware
│   ├── config.py        # Settings via pydantic-settings (.env)
│   ├── database.py      # Async engine + session factory
│   ├── models.py        # SQLAlchemy ORM models
│   ├── schemas.py       # Pydantic v2 request/response schemas
│   ├── auth.py          # JWT, bcrypt, RBAC/ABAC dependencies
│   ├── crud.py          # Async DB operations (transaction-safe)
│   └── events.py        # Background analytics worker
├── alembic/
│   ├── env.py           # Async-aware Alembic config
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py   # Tables + indexes + seed data
├── tests/
│   ├── conftest.py      # Pytest fixtures (in-memory SQLite)
│   ├── test_auth.py
│   ├── test_tours.py
│   └── test_bookings.py # Includes race-condition test
├── .github/workflows/ci.yml
├── migrate_sqlite_to_pg.py   # One-shot SQLite → Postgres migration
├── Dockerfile
├── docker-compose.yml        # Local dev (Postgres container)
├── alembic.ini
├── requirements.txt
├── pytest.ini
├── .env.example
└── .gitignore
```

---

## Seed Credentials

| Role    | Email                  | Password    |
|---------|------------------------|-------------|
| admin   | admin@almatour.kz      | admin123    |
| guide   | guide@almatour.kz      | guide123    |
| tourist | tourist@almatour.kz    | tourist123  |

---

## Quick Start — Local (Docker Compose)

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env — for local docker-compose the DATABASE_URL is overridden automatically

# 2. Start Postgres + API
docker compose up --build

# 3. Migrations run automatically on startup (CMD in Dockerfile)
# To run manually:
docker compose exec api alembic upgrade head

# 4. API docs
open http://localhost:8000/docs
```

---

## Quick Start — Neon (Production)

```bash
# 1. Get your Neon connection string from console.neon.tech
# Format: postgresql+asyncpg://user:pass@ep-xxx.region.aws.neon.tech/dbname?ssl=require

# 2. Set up .env
cp .env.example .env
# Fill in DATABASE_URL with your Neon string
# Fill in JWT_SECRET_KEY with a long random string (openssl rand -hex 32)

# 3. Install deps
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 4. Apply migrations (creates all tables + seed users/tours)
alembic upgrade head

# 5. Run
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Neon SSL note
asyncpg requires SSL for Neon. Your `DATABASE_URL` must include `?ssl=require`:
```
DATABASE_URL=postgresql+asyncpg://neondb_owner:PASSWORD@ep-xxx.eu-central-1.aws.neon.tech/neondb?ssl=require
```

---

## Migrate Data from SQLite → Neon

```bash
# 1. Make sure alembic upgrade head has already been run
# 2. Run the migration script pointing at your old DB file
python migrate_sqlite_to_pg.py --sqlite src/almatour.db
```

The script reads all tables from SQLite and upserts them into Postgres,
skipping conflicts. Password hashes are migrated as-is (SHA-256 from the old
app). `app/auth.py` includes a legacy SHA-256 fallback so existing users can
still log in. After migration, encourage users to change passwords so their
hashes are upgraded to bcrypt automatically on next login.

---

## Running Tests

```bash
pip install aiosqlite  # needed for in-memory SQLite in tests
pytest -v
```

Tests use an in-memory SQLite database — no Postgres needed locally.

---

## API Endpoints

### Auth
```bash
# Login → get JWT token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"tourist@almatour.kz","password":"tourist123"}'
# → {"token":"eyJ...","role":"tourist","name":"James Smith"}

export TOKEN="eyJ..."
```

### Tours
```bash
# List all active tours (paginated)
curl http://localhost:8000/tours \
  -H "Authorization: Bearer $TOKEN"

# Search tours by text
curl "http://localhost:8000/tours?search_text=Canyon" \
  -H "Authorization: Bearer $TOKEN"

# Spatial query — tours within 15km of a coordinate
curl "http://localhost:8000/tours?lat=43.25&lng=76.94&radius_km=15" \
  -H "Authorization: Bearer $TOKEN"

# Filter by H3 region
curl "http://localhost:8000/tours?h3_region=85304c49fffffff" \
  -H "Authorization: Bearer $TOKEN"

# Create a tour (guide/admin only)
curl -X POST http://localhost:8000/tours \
  -H "Authorization: Bearer $GUIDE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Kaindy Lake Trek",
    "description": "Crystal clear lake with submerged trees",
    "price": 60000,
    "capacity": 12,
    "lat": 42.9917,
    "lng": 78.4600,
    "location_name": "Kaindy Lake",
    "schedule_date": "2026-08-15"
  }'
```

### Bookings
```bash
# Book a tour
curl -X POST http://localhost:8000/bookings \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tour_id": 1, "seats": 2}'

# My bookings
curl http://localhost:8000/bookings/me \
  -H "Authorization: Bearer $TOKEN"
```

### Admin
```bash
# H3 analytics (admin only)
curl http://localhost:8000/analytics/h3 \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Audit log
curl http://localhost:8000/admin/audit-log \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Architecture Decisions

### Why async SQLAlchemy 2.0 + asyncpg?
FastAPI is async-first. Synchronous SQLAlchemy blocks the event loop on every
DB call, creating a bottleneck under concurrent load. The async engine lets the
server handle other requests while waiting for DB I/O.

### Race condition fix: SELECT ... FOR UPDATE
The original SQLite app had a race condition: two simultaneous booking requests
could both pass the `seats_available >= seats` check before either decremented.
The fix uses Postgres row-level locking:
```python
select(Tour).where(...).with_for_update()
```
This acquires an exclusive lock on the tour row for the duration of the
transaction. The second concurrent request blocks until the first commits,
then sees the updated seat count and correctly returns 400.

### Background analytics worker
**Dev (current):** FastAPI `BackgroundTasks` — runs after the response is
sent, zero extra dependencies.  
**Production recommendation:** Replace with **ARQ** (async Redis queue):
```bash
pip install arq redis
# Define worker, push jobs via arq.create_pool()
# Run separately: arq app.worker.WorkerSettings
```
This survives server crashes, supports retries, and scales independently.

### JWT vs session tokens
The original app stored opaque tokens in a `sessions` DB table (requiring a
DB lookup on every request). This version uses **signed JWT tokens** — the
server verifies the signature cryptographically with no DB round-trip per
request. The `sessions` table is kept in the schema for potential legacy
compatibility.

### Neon serverless
Neon's serverless Postgres scales to zero between requests, making it ideal for
a student/demo deployment. The `pool_pre_ping=True` on the engine handles
cold-start reconnection transparently.
