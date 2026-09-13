from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.database import close_db, init_db
from app.main import app


@pytest.fixture
async def client(tmp_path):
    settings.DB_PATH = str(tmp_path / "api_test.db")
    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await close_db()


async def test_create_and_list_monitor(client):
    resp = await client.post(
        "/api/monitors",
        json={"name": "Test TCP", "type": "tcp", "target": "127.0.0.1:1", "interval_seconds": 60},
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Test TCP"
    assert created["status"] == "pending"

    resp = await client.get("/api/monitors")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_get_missing_monitor_returns_404(client):
    resp = await client.get("/api/monitors/999")
    assert resp.status_code == 404


async def test_update_monitor(client):
    created = (
        await client.post(
            "/api/monitors", json={"name": "Original", "type": "http", "target": "http://localhost", "interval_seconds": 60}
        )
    ).json()

    resp = await client.put(f"/api/monitors/{created['id']}", json={"name": "Renombrado", "active": False})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Renombrado"
    assert resp.json()["status"] == "paused"


async def test_delete_monitor(client):
    created = (
        await client.post(
            "/api/monitors", json={"name": "Borrar", "type": "http", "target": "http://localhost", "interval_seconds": 60}
        )
    ).json()

    resp = await client.delete(f"/api/monitors/{created['id']}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/monitors/{created['id']}")
    assert resp.status_code == 404


async def test_checks_and_incidents_empty_for_new_monitor(client):
    created = (
        await client.post(
            "/api/monitors", json={"name": "Nuevo", "type": "http", "target": "http://localhost", "interval_seconds": 60}
        )
    ).json()

    resp = await client.get(f"/api/monitors/{created['id']}/checks")
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.get(f"/api/monitors/{created['id']}/incidents")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_notification_channel_crud(client):
    resp = await client.post(
        "/api/notifications",
        json={"type": "webhook", "name": "n8n", "config": {"url": "http://localhost/hook"}, "active": True},
    )
    assert resp.status_code == 201
    channel_id = resp.json()["id"]

    resp = await client.get("/api/notifications")
    assert len(resp.json()) == 1

    resp = await client.delete(f"/api/notifications/{channel_id}")
    assert resp.status_code == 204


async def test_export_import_roundtrip(client):
    await client.post(
        "/api/monitors", json={"name": "Exportable", "type": "dns", "target": "example.com", "interval_seconds": 120}
    )
    await client.post(
        "/api/notifications", json={"type": "webhook", "name": "hook", "config": {"url": "http://x"}, "active": True}
    )

    export_resp = await client.get("/api/export")
    assert export_resp.status_code == 200
    bundle = export_resp.json()
    assert len(bundle["monitors"]) == 1
    assert len(bundle["notification_channels"]) == 1

    import_resp = await client.post("/api/import", json=bundle)
    assert import_resp.status_code == 200
    assert import_resp.json() == {"monitors_imported": 1, "channels_imported": 1}

    resp = await client.get("/api/monitors")
    assert len(resp.json()) == 2  # el original + el importado


async def test_status_page_only_lists_active_monitors(client):
    await client.post(
        "/api/monitors", json={"name": "Activo", "type": "http", "target": "http://localhost", "interval_seconds": 60}
    )
    await client.post(
        "/api/monitors",
        json={"name": "Inactivo", "type": "http", "target": "http://localhost", "interval_seconds": 60, "active": False},
    )

    resp = await client.get("/api/status-page")
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()["monitors"]]
    assert names == ["Activo"]
