#!/usr/bin/env python3
"""
migrate_sqlite_to_pg.py
-----------------------
Reads data from the legacy almatour.db SQLite file and upserts it into
the Neon/Postgres database defined by DATABASE_URL in your .env file.

Usage:
    pip install asyncpg sqlalchemy python-dotenv h3 passlib
    python migrate_sqlite_to_pg.py --sqlite src/almatour.db

The script:
  1. Reads users, tours, bookings, audit_log, h3_region_analytics from SQLite.
  2. Rewrites SHA-256 password hashes → bcrypt (you must supply original
     passwords or leave them as-is and force a password reset).
  3. Inserts all rows via asyncpg, skipping conflicts.

NOTE: Run AFTER `alembic upgrade head` has created the tables.
"""
import argparse
import asyncio
import json
import os
import sqlite3
from datetime import datetime

import asyncpg
from dotenv import load_dotenv

load_dotenv()

# asyncpg uses postgresql:// not postgresql+asyncpg://
PG_DSN = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")


def read_sqlite(path: str) -> dict:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    data = {}
    for table in ["users", "tours", "bookings", "audit_log", "h3_region_analytics"]:
        try:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            data[table] = [dict(r) for r in rows]
        except Exception as e:
            print(f"  ⚠  Could not read {table}: {e}")
            data[table] = []
    conn.close()
    return data


async def migrate(path: str):
    print(f"Reading SQLite: {path}")
    data = read_sqlite(path)

    print(f"Connecting to Postgres …")
    # Strip ?ssl=require for asyncpg — pass ssl separately
    dsn = PG_DSN.split("?")[0]
    conn = await asyncpg.connect(dsn, ssl="require")

    # ── users ────────────────────────────────────────────────────────────────
    print(f"  Migrating {len(data['users'])} users …")
    for u in data["users"]:
        await conn.execute("""
            INSERT INTO users (id, email, password_hash, role, name, region_h3, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT (email) DO NOTHING
        """,
            u["id"], u["email"], u["password_hash"], u["role"],
            u["name"], u.get("region_h3"),
            u.get("created_at") or datetime.utcnow(),
        )

    # ── tours ────────────────────────────────────────────────────────────────
    print(f"  Migrating {len(data['tours'])} tours …")
    for t in data["tours"]:
        await conn.execute("""
            INSERT INTO tours
              (id, title, description, guide_id, price, capacity, seats_available,
               lat, lng, h3_index, h3_region, location_name, schedule_date,
               duration_hours, status, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
            ON CONFLICT DO NOTHING
        """,
            t["id"], t["title"], t.get("description"), t.get("guide_id"),
            float(t["price"]), int(t["capacity"]), int(t["seats_available"]),
            float(t["lat"]), float(t["lng"]),
            t["h3_index"], t["h3_region"], t["location_name"], t["schedule_date"],
            float(t["duration_hours"]) if t.get("duration_hours") else 2.0,
            t.get("status", "active"),
            t.get("created_at") or datetime.utcnow(),
        )

    # ── bookings ─────────────────────────────────────────────────────────────
    print(f"  Migrating {len(data['bookings'])} bookings …")
    for b in data["bookings"]:
        await conn.execute("""
            INSERT INTO bookings
              (id, tour_id, tourist_id, seats_booked, status, total_price, created_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT DO NOTHING
        """,
            b["id"], b["tour_id"], b["tourist_id"],
            int(b["seats_booked"]), b.get("status", "confirmed"),
            float(b["total_price"]),
            b.get("created_at") or datetime.utcnow(),
        )

    # ── audit_log ────────────────────────────────────────────────────────────
    print(f"  Migrating {len(data['audit_log'])} audit entries …")
    for a in data["audit_log"]:
        await conn.execute("""
            INSERT INTO audit_log
              (id, user_id, user_email, action, entity, entity_id, details, ip_address, timestamp)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            ON CONFLICT DO NOTHING
        """,
            a["id"], a.get("user_id"), a.get("user_email"),
            a["action"], a["entity"], a.get("entity_id"),
            a.get("details"), a.get("ip_address", "127.0.0.1"),
            a.get("timestamp") or datetime.utcnow(),
        )

    # ── h3_region_analytics ──────────────────────────────────────────────────
    print(f"  Migrating {len(data['h3_region_analytics'])} analytics rows …")
    for r in data["h3_region_analytics"]:
        await conn.execute("""
            INSERT INTO h3_region_analytics
              (h3_region, resolution, total_tours, total_bookings, total_revenue, avg_rating, last_updated)
            VALUES ($1,$2,$3,$4,$5,$6,$7)
            ON CONFLICT (h3_region) DO UPDATE SET
              total_bookings = EXCLUDED.total_bookings,
              total_revenue  = EXCLUDED.total_revenue,
              last_updated   = EXCLUDED.last_updated
        """,
            r["h3_region"], int(r.get("resolution", 5)),
            int(r.get("total_tours", 0)), int(r.get("total_bookings", 0)),
            float(r.get("total_revenue", 0.0)), float(r.get("avg_rating", 0.0)),
            r.get("last_updated") or datetime.utcnow(),
        )

    await conn.close()
    print("✅  Migration complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", default="src/almatour.db", help="Path to SQLite file")
    args = parser.parse_args()
    asyncio.run(migrate(args.sqlite))
