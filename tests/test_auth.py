import pytest


@pytest.mark.asyncio
async def test_login_success(client):
    r = await client.post("/auth/login", json={"email": "admin@test.kz", "password": "admin123"})
    assert r.status_code == 200
    body = r.json()
    assert "token" in body
    assert body["role"] == "admin"


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    r = await client.post("/auth/login", json={"email": "admin@test.kz", "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_empty_fields(client):
    r = await client.post("/auth/login", json={"email": "", "password": ""})
    assert r.status_code == 422  # Pydantic validation


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    r = await client.post("/auth/login", json={"email": "ghost@test.kz", "password": "x"})
    assert r.status_code == 401
