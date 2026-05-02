from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator


# ── Auth ─────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    token: str
    role: str
    name: str


# ── Tours ─────────────────────────────────────────────────────────────────────

class TourCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(max_length=4000)
    price: float = Field(gt=0, le=10_000_000)
    image_url: Optional[str] = None
    badge: Optional[str] = "Nature"
    capacity: int = Field(gt=0, le=10_000)
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    location_name: str = Field(min_length=2, max_length=255)
    schedule_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    duration_hours: Optional[float] = Field(default=2.0, ge=0.25, le=168)


class TourUpdate(BaseModel):
    price: Optional[float] = Field(default=None, gt=0)
    seats_available: Optional[int] = Field(default=None, ge=0)
    status: Optional[str] = Field(default=None, pattern="^(active|cancelled|completed)$")


class TourOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    guide_id: Optional[int]
    image_url: Optional[str] = None
    badge: Optional[str] = None
    price: float
    capacity: int
    seats_available: int
    lat: float
    lng: float
    h3_index: str
    h3_region: str
    location_name: str
    schedule_date: str
    duration_hours: Optional[float]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ToursListResponse(BaseModel):
    source: str = "full_list"
    total: int
    page: int
    per_page: int
    tours: list[TourOut]


# ── Bookings ──────────────────────────────────────────────────────────────────

class BookingCreate(BaseModel):
    tour_id: int
    seats: int = Field(default=1, ge=1, le=50)


class BookingOut(BaseModel):
    id: int
    tour_id: int
    tourist_id: int
    seats_booked: int
    status: str
    total_price: float
    created_at: datetime
    # joined fields
    title: Optional[str] = None
    location_name: Optional[str] = None
    h3_index: Optional[str] = None
    schedule_date: Optional[str] = None

    model_config = {"from_attributes": True}


class BookingResponse(BaseModel):
    booking_id: int
    total_price: float
    status: str


# ── Analytics ─────────────────────────────────────────────────────────────────

class H3RegionStat(BaseModel):
    h3_region: str
    resolution: int
    total_tours: int
    total_bookings: int
    total_revenue: float
    avg_rating: float
    last_updated: datetime
    center_lat: Optional[float] = None
    center_lng: Optional[float] = None

    model_config = {"from_attributes": True}


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditLogEntry(BaseModel):
    id: int
    user_id: Optional[int]
    user_email: Optional[str]
    action: str
    entity: str
    entity_id: Optional[int]
    details: Optional[str]
    ip_address: str
    timestamp: datetime

    model_config = {"from_attributes": True}
