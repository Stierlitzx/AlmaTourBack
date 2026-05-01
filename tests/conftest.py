"""
Pytest fixtures.

Uses an in-memory SQLite database so tests run without a real Postgres instance.
SQLAlchemy 2.0 async + aiosqlite.
"""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(engine):
    """AsyncClient wired to the app with test DB injected."""
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # Seed minimal data
    async with factory() as session:
        from passlib.context import CryptContext
        pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
        from app.models import User, Tour
        admin = User(email="admin@test.kz", password_hash=pwd.hash("admin123"),
                     role="admin", name="Test Admin")
        tourist = User(email="tourist@test.kz", password_hash=pwd.hash("tourist123"),
                       role="tourist", name="Test Tourist")
        guide = User(email="guide@test.kz", password_hash=pwd.hash("guide123"),
                     role="guide", name="Test Guide")
        session.add_all([admin, tourist, guide])
        await session.flush()

        import h3
        tour = Tour(
            title="Test Canyon Tour", description="A test tour",
            guide_id=guide.id, price=50000, capacity=10, seats_available=10,
            lat=43.35, lng=79.07,
            h3_index=h3.latlng_to_cell(43.35, 79.07, 8),
            h3_region=h3.latlng_to_cell(43.35, 79.07, 5),
            location_name="Charyn", schedule_date="2026-09-01",
        )
        session.add(tour)
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
