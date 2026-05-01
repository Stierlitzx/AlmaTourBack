import pytest


async def _token(client, email, password):
    r = await client.post("/auth/login", json={"email": email, "password": password})
    return r.json()["token"]


@pytest.mark.asyncio
async def test_list_tours(client):
    token = await _token(client, "tourist@test.kz", "tourist123")
    r = await client.get("/tours", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert "tours" in body
    assert body["total"] >= 1


@pytest.mark.asyncio
async def test_list_tours_search(client):
    token = await _token(client, "tourist@test.kz", "tourist123")
    r = await client.get(
        "/tours", params={"search_text": "Canyon"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    tours = r.json()["tours"]
    assert all("canyon" in t["title"].lower() or "canyon" in (t["description"] or "").lower()
               for t in tours)


@pytest.mark.asyncio
async def test_create_tour_as_guide(client):
    token = await _token(client, "guide@test.kz", "guide123")
    payload = {
        "title": "New Alpine Trek",
        "description": "Beautiful mountain trek",
        "price": 35000,
        "capacity": 8,
        "lat": 43.14,
        "lng": 77.08,
        "location_name": "Tian Shan",
        "schedule_date": "2026-10-01",
    }
    r = await client.post("/tours", json=payload,
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    assert "h3_index" in r.json()


@pytest.mark.asyncio
async def test_create_tour_as_tourist_forbidden(client):
    token = await _token(client, "tourist@test.kz", "tourist123")
    payload = {
        "title": "Sneaky Tour", "description": "x",
        "price": 1000, "capacity": 1,
        "lat": 43.0, "lng": 77.0,
        "location_name": "Nowhere", "schedule_date": "2026-12-01",
    }
    r = await client.post("/tours", json=payload,
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_list_tours_unauthenticated(client):
    r = await client.get("/tours")
    assert r.status_code == 403
