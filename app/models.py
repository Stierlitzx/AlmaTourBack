from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, Float, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False,
        # CHECK constraint — Postgres enforces this
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    region_h3: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("role IN ('tourist','guide','admin')", name="ck_users_role"),
    )

    tours: Mapped[list["Tour"]] = relationship("Tour", back_populates="guide")
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="tourist")
    sessions: Mapped[list["Session"]] = relationship("Session", back_populates="user")


class Tour(Base):
    __tablename__ = "tours"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    guide_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    price: Mapped[float] = mapped_column(Float, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    seats_available: Mapped[int] = mapped_column(Integer, nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    h3_index: Mapped[str] = mapped_column(String(20), nullable=False, index=True)   # res 8
    h3_region: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # res 5
    location_name: Mapped[str] = mapped_column(String(255), nullable=False)
    schedule_date: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    duration_hours: Mapped[float | None] = mapped_column(Float, nullable=True, default=2.0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('active','cancelled','completed')", name="ck_tours_status"),
    )

    guide: Mapped["User"] = relationship("User", back_populates="tours")
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="tour")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tour_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tours.id", ondelete="CASCADE"), nullable=False
    )
    tourist_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    seats_booked: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="confirmed")
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("status IN ('confirmed','cancelled')", name="ck_bookings_status"),
    )

    tour: Mapped["Tour"] = relationship("Tour", back_populates="bookings")
    tourist: Mapped["User"] = relationship("User", back_populates="bookings")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    user_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    ip_address: Mapped[str] = mapped_column(String(50), nullable=False, server_default="'127.0.0.1'")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class H3RegionAnalytics(Base):
    __tablename__ = "h3_region_analytics"

    h3_region: Mapped[str] = mapped_column(String(20), primary_key=True)
    resolution: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    total_tours: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_bookings: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_revenue: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    avg_rating: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(String(512), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="sessions")
