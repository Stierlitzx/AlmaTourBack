# AlmaTour — Async FastAPI + PostgreSQL/Neon backend

This repository contains the current AlmaTour backend implementation:

- FastAPI 0.111
- async SQLAlchemy 2.0 + asyncpg
- PostgreSQL / Neon Serverless Postgres
- JWT authentication with bcrypt passwords
- H3-based spatial filtering and analytics

---

## Project structure

```text
AlmaTourBack/
├── app/
│   ├── main.py        # FastAPI app, routes, middleware, lifespan
│   ├── config.py      # Settings loaded from .env
│   ├── database.py    # Async engine + session factory
│   ├── models.py      # SQLAlchemy ORM models
│   ├── schemas.py     # Pydantic request/response models
│   ├── auth.py        # JWT, bcrypt, RBAC/ABAC helpers
│   ├── crud.py        # Async DB operations
│   └── events.py      # Background analytics task
├── alembic/
│   ├── env.py
│   └── versions/
│       └── 0001_initial_schema.py
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_tours.py
│   └── test_bookings.py
├── .github/workflows/ci.yml
├── docker-compose.yml
├── Dockerfile
├── migrate_sqlite_to_pg.py
├── requirements.txt
├── pytest.ini
├── .env.example
└── utility scripts (e.g. `seed_tours.py`, `check_tours.py`, `fix_passwords.py`)
```

---

## Environment setup

Copy the example file and configure your database connection:

```powershell
Copy-Item .env.example .env
```

On macOS/Linux the equivalent command is:

```bash
cp .env.example .env
```

Important variables:

- `DATABASE_URL` — PostgreSQL/Neon connection string
- `JWT_SECRET_KEY` — long random secret for JWT signing
- `APP_ENV` — `development` / `test` / `production`
- `CORS_ORIGINS` — comma-separated allowed origins

### Neon / PostgreSQL URL format

The app accepts URLs such as:

```text
postgresql+asyncpg://user:pass@host/dbname?ssl=require
```

It also normalizes common Neon-style URLs that use `postgres://` or `sslmode=require`.

---

## Run locally with Docker Compose

```bash
docker compose up --build
```

This starts:

- Postgres on `localhost:5432`
- API on `localhost:8000`

Open the docs at:

```text
http://localhost:8000/docs
```

### Note about startup behavior

The current `Dockerfile` starts the app with `alembic stamp head` and then launches Uvicorn.
The application itself also verifies the ORM tables on startup via `Base.metadata.create_all()`.

If you want to apply the Alembic migration manually on a fresh database, run:

```bash
alembic upgrade head
```

---

## Run locally without Docker

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

If you are using Windows PowerShell, remember that the virtual environment activation command is:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

## Database and migrations

The initial schema and demo seed data live in:

- `alembic/versions/0001_initial_schema.py`

That migration creates the following tables:

- `users`
- `tours`
- `bookings`
- `audit_log`
- `h3_region_analytics`
- `sessions`

It also seeds demo users and tours.

### Demo credentials

| Role | Email | Password |
|---|---|---|
| admin | `admin@almatour.kz` | `admin123` |
| guide | `guide@almatour.kz` | `guide123` |
| tourist | `tourist@almatour.kz` | `tourist123` |

---

## Migrating data from the legacy SQLite app

The repo includes a one-shot helper:

```bash
python migrate_sqlite_to_pg.py --sqlite src/almatour.db
```

What it does:

- reads `users`, `tours`, `bookings`, `audit_log`, and `h3_region_analytics`
- upserts rows into Postgres
- keeps legacy password hashes as-is

The current auth code can verify both bcrypt and legacy SHA-256 hashes.

---

## Running tests

The test suite uses in-memory SQLite and does not require a real Postgres instance.

Install the extra test dependency used by the fixtures:

```bash
pip install aiosqlite
```

Then run:

```bash
pytest -v
```

`pytest.ini` enables asyncio auto mode and points pytest at `tests/`.

---

## Postman smoke test

Import these files into Postman:

- `postman/AlmaTour_smoke_test.postman_collection.json`
- `postman/AlmaTour_local.postman_environment.json`

Then select the `AlmaTour Local` environment and run the collection top to bottom.

The smoke test covers:

- `GET /health`
- `POST /auth/login`
- `GET /tours`
- `POST /bookings`
- `GET /bookings/me`
- `DELETE /bookings/{booking_id}`

You can change `baseUrl`, credentials, or runtime variables (`token`, `tourId`, `bookingId`) in the environment.

---

## API overview

### Auth

- `POST /auth/login`
- `POST /auth/register`

### Tours

- `GET /tours`
- `POST /tours`
- `PATCH /tours/{tour_id}`

### Bookings

- `POST /bookings`
- `GET /bookings/me`
- `DELETE /bookings/{booking_id}`

### Analytics / admin

- `GET /analytics/h3`
- `GET /admin/audit-log`

### Meta

- `GET /health`
- `GET /` redirects to `/docs`

---

## Example requests

### Login

```powershell
curl.exe -X POST http://localhost:8000/auth/login -H "Content-Type: application/json" -d '{"email":"tourist@almatour.kz","password":"tourist123"}'
```

The response contains `token`, `role`, and `name`.

### Register

```powershell
curl.exe -X POST http://localhost:8000/auth/register -H "Content-Type: application/json" -d '{"name":"New Tourist","email":"new@example.com","password":"secret123"}'
```

### List tours

```powershell
curl.exe http://localhost:8000/tours -H "Authorization: Bearer $TOKEN"
```

Supported query params:

- `search_text`
- `h3_region`
- `lat`, `lng`, `radius_km`
- `page`, `per_page`

### Create a tour

```powershell
curl.exe -X POST http://localhost:8000/tours -H "Authorization: Bearer $GUIDE_TOKEN" -H "Content-Type: application/json" -d '{"title":"Kaindy Lake Trek","description":"Crystal clear lake with submerged trees","price":60000,"capacity":12,"lat":42.9917,"lng":78.46,"location_name":"Kaindy Lake","schedule_date":"2026-08-15"}'
```

### Book a tour

```powershell
curl.exe -X POST http://localhost:8000/bookings -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"tour_id":1,"seats":2}'
```

### My bookings

```powershell
curl.exe http://localhost:8000/bookings/me -H "Authorization: Bearer $TOKEN"
```

---

## Authorization model

The app uses JWT bearer tokens and role-based permissions:

- `tourist` can read tours and create bookings
- `guide` can create tours and update their own tours
- `admin` can access analytics and the audit log

Booking seat counts are protected with `SELECT ... FOR UPDATE` to avoid overbooking under concurrent load.

---

## CI

The GitHub Actions workflow runs:

- dependency installation
- `ruff check app/ tests/`
- `pytest -v`

---

## Useful files

- `app/main.py` — API routes and middleware
- `app/auth.py` — JWT + role checks
- `app/crud.py` — database operations
- `app/config.py` — environment handling
- `alembic/versions/0001_initial_schema.py` — schema and seed data
- `tests/conftest.py` — async SQLite test fixtures

---

## Health check

```powershell
curl.exe http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```
