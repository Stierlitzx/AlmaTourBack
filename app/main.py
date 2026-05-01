"""
AlmaTour — async FastAPI backend
Postgres/Neon edition
"""
import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

import h3
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.auth import (
    assert_guide_owns_tour,
    create_access_token,
    require_permission,
    verify_password,
)
from app.config import get_settings
from app.database import engine, get_db
from app.events import process_booking_confirmed
from app.models import Base
from app.schemas import (
    AuditLogEntry,
    BookingCreate,
    BookingOut,
    BookingResponse,
    H3RegionStat,
    LoginRequest,
    TokenResponse,
    TourCreate,
    TourOut,
    TourUpdate,
    ToursListResponse,
)

settings = get_settings()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("AlmaTour")


# ── Lifespan (replaces on_event) ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist (Alembic handles migrations in prod)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("AlmaTour started — database tables verified")
    yield
    await engine.dispose()


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AlmaTour API",
    version="2.0.0",
    description="Async FastAPI backend with H3 spatial indexing on PostgreSQL/Neon",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.cors_origins == "*" else settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request logging middleware ────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    logger.info("→ %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
        ms = (time.perf_counter() - start) * 1000
        logger.info(
            "← %s %s  status=%s  %.1fms",
            request.method, request.url.path, response.status_code, ms,
        )
        return response
    except Exception as exc:
        ms = (time.perf_counter() - start) * 1000
        logger.error(
            "✗ %s %s  error=%s  %.1fms",
            request.method, request.url.path, exc, ms,
        )
        raise


# ── Helper: client IP ─────────────────────────────────────────────────────────
def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host or "unknown")


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Meta"])
async def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root_redirect():
    """Redirect browser root / to the interactive docs at /docs."""
    return RedirectResponse(url="/docs")


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await crud.get_user_by_email(db, req.email)
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "role": user.role})

    await crud.write_audit(
        db, user.id, user.email, "LOGIN", "session",
        details={"role": user.role}, ip_address=client_ip(request),
    )
    await db.commit()
    return TokenResponse(token=token, role=user.role, name=user.name)


# ── Tours ─────────────────────────────────────────────────────────────────────

@app.get("/tours", response_model=ToursListResponse, tags=["Tours"])
async def list_tours(
    search_text: Optional[str] = None,
    h3_region: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: float = 10.0,
    page: int = 0,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("read:tours")),
):
    tours, source = await crud.list_tours(
        db, search_text, h3_region, lat, lng, radius_km, page, per_page
    )
    total = await crud.count_tours(db, search_text, h3_region)
    return ToursListResponse(
        source=source, total=total, page=page, per_page=per_page,
        tours=[TourOut.model_validate(t) for t in tours],
    )


@app.post("/tours", response_model=dict, status_code=201, tags=["Tours"])
async def create_tour(
    body: TourCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("create:tour")),
):
    try:
        tour = await crud.create_tour(db, body, user["user_id"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"H3 computation failed: {exc}")

    await crud.write_audit(
        db, user["user_id"], user["email"], "CREATE_TOUR", "tour", tour.id,
        details={"title": tour.title, "h3_index": tour.h3_index},
        ip_address=client_ip(request),
    )
    await db.commit()
    return {"id": tour.id, "h3_index": tour.h3_index, "h3_region": tour.h3_region}


@app.patch("/tours/{tour_id}", tags=["Tours"])
async def patch_tour(
    tour_id: int,
    body: TourUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("create:tour")),
):
    await assert_guide_owns_tour(tour_id, user, db)
    updated = await crud.update_tour(db, tour_id, body)
    if not updated:
        raise HTTPException(status_code=400, detail="Nothing to update")
    await crud.write_audit(
        db, user["user_id"], user["email"], "UPDATE_TOUR", "tour", tour_id,
        details=body.model_dump(exclude_none=True), ip_address=client_ip(request),
    )
    await db.commit()
    return {"updated": True}


# ── Bookings ──────────────────────────────────────────────────────────────────

@app.post("/bookings", response_model=BookingResponse, status_code=201, tags=["Bookings"])
async def create_booking(
    body: BookingCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("create:booking")),
):
    try:
        booking, tour = await crud.create_booking_atomic(db, body, user["user_id"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    await crud.write_audit(
        db, user["user_id"], user["email"], "CREATE_BOOKING", "booking", booking.id,
        details={"tour_id": body.tour_id, "seats": body.seats, "total": booking.total_price},
        ip_address=client_ip(request),
    )
    await db.commit()

    # Fire-and-forget analytics update (background, does NOT block response)
    from app.database import AsyncSessionLocal
    background_tasks.add_task(
        process_booking_confirmed,
        h3_region=tour.h3_region,
        revenue=booking.total_price,
        booking_id=booking.id,
        db=AsyncSessionLocal(),
    )

    return BookingResponse(
        booking_id=booking.id,
        total_price=booking.total_price,
        status=booking.status,
    )


@app.get("/bookings/me", tags=["Bookings"])
async def get_my_bookings(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("read:booking_own")),
):
    bookings = await crud.my_bookings(db, user["user_id"])
    result = []
    for b in bookings:
        d = BookingOut.model_validate(b)
        if b.tour:
            d.title = b.tour.title
            d.location_name = b.tour.location_name
            d.h3_index = b.tour.h3_index
            d.schedule_date = b.tour.schedule_date
        result.append(d)
    return {"bookings": result}


# ── Analytics ─────────────────────────────────────────────────────────────────

@app.get("/analytics/h3", tags=["Analytics"])
async def h3_analytics(
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("read:analytics")),
):
    rows = await crud.get_h3_analytics(db)
    enriched = []
    for r in rows:
        stat = H3RegionStat.model_validate(r)
        try:
            center = h3.cell_to_latlng(r.h3_region)
            stat.center_lat, stat.center_lng = center[0], center[1]
        except Exception:
            pass
        enriched.append(stat)
    return {"h3_region_stats": enriched}


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.get("/admin/audit-log", tags=["Admin"])
async def audit_log(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("read:audit_log")),
):
    rows = await crud.get_audit_log(db, limit)
    return {"audit_log": [AuditLogEntry.model_validate(r) for r in rows]}


# ── Dev entrypoint ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
