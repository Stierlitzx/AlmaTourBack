"""initial schema + seed

Revision ID: 0001
Revises: 
Create Date: 2026-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("region_h3", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('tourist','guide','admin')", name="ck_users_role"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── tours ────────────────────────────────────────────────────────────────
    op.create_table(
        "tours",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("guide_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("seats_available", sa.Integer(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("h3_index", sa.String(20), nullable=False),
        sa.Column("h3_region", sa.String(20), nullable=False),
        sa.Column("location_name", sa.String(255), nullable=False),
        sa.Column("schedule_date", sa.String(20), nullable=False),
        sa.Column("duration_hours", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('active','cancelled','completed')", name="ck_tours_status"),
    )
    op.create_index("ix_tours_h3_index", "tours", ["h3_index"])
    op.create_index("ix_tours_h3_region", "tours", ["h3_region"])
    op.create_index("ix_tours_schedule_date", "tours", ["schedule_date"])

    # ── bookings ─────────────────────────────────────────────────────────────
    op.create_table(
        "bookings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tour_id", sa.BigInteger(), sa.ForeignKey("tours.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tourist_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seats_booked", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="confirmed"),
        sa.Column("total_price", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('confirmed','cancelled')", name="ck_bookings_status"),
    )
    op.create_index("ix_bookings_tourist_id", "bookings", ["tourist_id"])

    # ── audit_log ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("user_email", sa.String(255), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity", sa.String(100), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=False, server_default="'127.0.0.1'"),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── h3_region_analytics ──────────────────────────────────────────────────
    op.create_table(
        "h3_region_analytics",
        sa.Column("h3_region", sa.String(20), primary_key=True),
        sa.Column("resolution", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("total_tours", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_bookings", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_revenue", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("avg_rating", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── sessions (kept for potential legacy token support) ───────────────────
    op.create_table(
        "sessions",
        sa.Column("token", sa.String(512), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── seed data ─────────────────────────────────────────────────────────────
    # Passwords are bcrypt hashes of: admin123 / guide123 / tourist123
    # (generated with passlib.context.CryptContext(schemes=["bcrypt"]).hash(...))
    op.execute("""
        INSERT INTO users (email, password_hash, role, name, region_h3) VALUES
        ('admin@almatour.kz',
         '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6o8kOJ1yHe',
         'admin', 'System Admin', NULL),
        ('guide@almatour.kz',
         '$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uXkwAZPrW',
         'guide', 'Aidana Bekova', '852830fffffffffff'),
        ('tourist@almatour.kz',
         '$2b$12$PehCVXoJuNpKaGMWdZjbGurx6tDLM5XZ.S9bODjFJPn5NkqH/5kEu',
         'tourist', 'James Smith', '852830fffffffffff')
        ON CONFLICT DO NOTHING;
    """)

    # Seed tours (guide_id=2 = Aidana Bekova)
    op.execute("""
        INSERT INTO tours
          (title, description, guide_id, price, capacity, seats_available,
           lat, lng, h3_index, h3_region, location_name, schedule_date, duration_hours)
        VALUES
          ('Shymbulak Mountain Tour',
           'Cable car ride & ski resort visit', 2, 45000, 10, 10,
           43.1393, 77.0785, '88304c49bdfffff', '85304c4bfffffff',
           'Shymbulak, Almaty', '2026-07-15', 6),
          ('Medeu Ice Rink Experience',
           'World''s highest skating rink outdoor visit', 2, 25000, 20, 20,
           43.1560, 77.0572, '88304c49bdfffff', '85304c4bfffffff',
           'Medeu, Almaty', '2026-07-20', 3),
          ('Kok-Tobe Cable Car & View',
           'Panoramic city views from Kok-Tobe Hill', 2, 30000, 15, 15,
           43.2335, 76.9720, '88304c4991fffff', '85304c49fffffff',
           'Kok-Tobe, Almaty', '2026-08-01', 2),
          ('Almaty Green Bazaar Food Tour',
           'Taste local cuisine at the historic bazaar', 2, 20000, 12, 12,
           43.2551, 76.9440, '88304c4991fffff', '85304c49fffffff',
           'Green Bazaar, Almaty', '2026-08-10', 3),
          ('Charyn Canyon Day Trip',
           'Spectacular canyon 200km from Almaty', 2, 80000, 8, 8,
           43.3503, 79.0700, '883048a6b1fffff', '853048a7fffffff',
           'Charyn Canyon', '2026-09-05', 12)
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    op.drop_table("sessions")
    op.drop_table("h3_region_analytics")
    op.drop_table("audit_log")
    op.drop_table("bookings")
    op.drop_table("tours")
    op.drop_table("users")
