"""
CRUD — async SQLAlchemy 2.0 database operations.

Booking uses SELECT ... FOR UPDATE to prevent race conditions on seats_available.
"""
import json
from datetime import datetime, timezone
from typing import Optional

import h3
from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Booking, H3RegionAnalytics, Tour, User
from app.schemas import BookingCreate, TourCreate, TourUpdate


# ── Auth / Users ──────────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


# ── Tours ─────────────────────────────────────────────────────────────────────

async def list_tours(
    db: AsyncSession,
    search_text: Optional[str] = None,
    h3_region: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = 10.0,
    page: int = 0,
    per_page: int = 20,
) -> tuple[list[Tour], str]:
    """
    Returns (tours, source_label).
    Uses parameterised queries exclusively — no string interpolation of user input.
    """
    stmt = select(Tour).where(Tour.status == "active")

    if lat is not None and lng is not None:
        center_cell = h3.latlng_to_cell(lat, lng, 8)
        k_rings = max(1, int(radius_km / 1.5))
        nearby_cells = list(h3.grid_disk(center_cell, k_rings))
        # Use ANY with a bound array parameter — fully safe
        stmt = stmt.where(Tour.h3_index.in_(nearby_cells))
        source = "h3_spatial_query"
    elif h3_region:
        stmt = stmt.where(Tour.h3_region == h3_region)
        source = "h3_region_filter"
    else:
        source = "full_list"

    if search_text:
        pattern = f"%{search_text}%"
        from sqlalchemy import or_
        stmt = stmt.where(or_(Tour.title.ilike(pattern), Tour.description.ilike(pattern)))

    stmt = stmt.offset(page * per_page).limit(per_page)
    result = await db.execute(stmt)
    return result.scalars().all(), source


async def count_tours(
    db: AsyncSession,
    search_text: Optional[str] = None,
    h3_region: Optional[str] = None,
) -> int:
    from sqlalchemy import func, or_
    stmt = select(func.count()).select_from(Tour).where(Tour.status == "active")
    if h3_region:
        stmt = stmt.where(Tour.h3_region == h3_region)
    if search_text:
        pattern = f"%{search_text}%"
        stmt = stmt.where(or_(Tour.title.ilike(pattern), Tour.description.ilike(pattern)))
    result = await db.execute(stmt)
    return result.scalar_one()


async def create_tour(db: AsyncSession, body: TourCreate, guide_id: int) -> Tour:
    h3_idx = h3.latlng_to_cell(body.lat, body.lng, 8)
    h3_reg = h3.latlng_to_cell(body.lat, body.lng, 5)
    tour = Tour(
        title=body.title,
        description=body.description,
        guide_id=guide_id,
        price=body.price,
        image_url=body.image_url,
        badge=body.badge,
        capacity=body.capacity,
        seats_available=body.capacity,
        lat=body.lat,
        lng=body.lng,
        h3_index=h3_idx,
        h3_region=h3_reg,
        location_name=body.location_name,
        schedule_date=body.schedule_date,
        duration_hours=body.duration_hours,
    )
    db.add(tour)
    await db.flush()  # get generated id without closing transaction
    return tour


async def update_tour(db: AsyncSession, tour_id: int, body: TourUpdate) -> bool:
    values: dict = {}
    if body.price is not None:
        values["price"] = body.price
    if body.seats_available is not None:
        values["seats_available"] = body.seats_available
    if body.status is not None:
        values["status"] = body.status
    if not values:
        return False
    await db.execute(update(Tour).where(Tour.id == tour_id).values(**values))
    return True


# ── Bookings — race-condition safe ────────────────────────────────────────────

async def create_booking_atomic(
    db: AsyncSession, body: BookingCreate, tourist_id: int
) -> Booking:
    """
    Uses SELECT ... FOR UPDATE to lock the tour row for the duration of
    the transaction, preventing double-booking under concurrent load.
    """
    # Lock the tour row in this transaction
    result = await db.execute(
        select(Tour)
        .where(Tour.id == body.tour_id, Tour.status == "active")
        .with_for_update()          # ← Postgres row-level lock
    )
    tour = result.scalar_one_or_none()
    if tour is None:
        raise ValueError("Tour not found or not active")
    if tour.seats_available < body.seats:
        raise ValueError(f"Only {tour.seats_available} seats available")

    total = tour.price * body.seats
    booking = Booking(
        tour_id=body.tour_id,
        tourist_id=tourist_id,
        seats_booked=body.seats,
        total_price=total,
        status="confirmed",
    )
    db.add(booking)
    tour.seats_available -= body.seats
    await db.flush()
    return booking, tour  # return tour so caller has h3_region


async def my_bookings(db: AsyncSession, tourist_id: int) -> list:
    from sqlalchemy.orm import joinedload
    result = await db.execute(
        select(Booking)
        .options(joinedload(Booking.tour))
        .where(Booking.tourist_id == tourist_id)
        .order_by(Booking.created_at.desc())
    )
    return result.scalars().all()


# ── Analytics ─────────────────────────────────────────────────────────────────

async def get_h3_analytics(db: AsyncSession) -> list[H3RegionAnalytics]:
    result = await db.execute(
        select(H3RegionAnalytics).order_by(H3RegionAnalytics.total_revenue.desc())
    )
    return result.scalars().all()


async def upsert_h3_analytics(db: AsyncSession, h3_region: str, revenue: float) -> None:
    """
    Upsert analytics for a region. Uses Postgres ON CONFLICT DO UPDATE
    via raw SQL for atomicity.
    """
    await db.execute(
        text("""
            INSERT INTO h3_region_analytics (h3_region, resolution, total_tours, total_bookings, total_revenue, last_updated)
            VALUES (:region, 5, 0, 1, :rev, now())
            ON CONFLICT (h3_region) DO UPDATE SET
                total_bookings = h3_region_analytics.total_bookings + 1,
                total_revenue  = h3_region_analytics.total_revenue + :rev,
                last_updated   = now()
        """),
        {"region": h3_region, "rev": revenue},
    )


# ── Audit Log ─────────────────────────────────────────────────────────────────

async def write_audit(
    db: AsyncSession,
    user_id: Optional[int],
    user_email: Optional[str],
    action: str,
    entity: str,
    entity_id: Optional[int] = None,
    details: Optional[dict] = None,
    ip_address: str = "127.0.0.1",
) -> None:
    entry = AuditLog(
        user_id=user_id,
        user_email=user_email,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details=json.dumps(details) if details else None,
        ip_address=ip_address,
    )
    db.add(entry)


async def get_audit_log(db: AsyncSession, limit: int = 50) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
    )
    return result.scalars().all()
