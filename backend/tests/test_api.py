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


async def test_check_now_runs_immediately(client, local_http_server):
    host, port = local_http_server
    created = (
        await client.post(
            "/api/monitors", json={"name": "CheckNow", "type": "tcp", "target": f"{host}:{port}", "interval_seconds": 60}
        )
    ).json()

    resp = await client.post(f"/api/monitors/{created['id']}/check-now")
    assert resp.status_code == 200
    assert resp.json()["status"] == "up"

    checks = (await client.get(f"/api/monitors/{created['id']}/checks")).json()
    assert len(checks) == 1


async def test_check_now_missing_monitor_404(client):
    resp = await client.post("/api/monitors/999/check-now")
    assert resp.status_code == 404


async def test_reset_history_clears_data_but_keeps_monitor(client, local_http_server):
    host, port = local_http_server
    created = (
        await client.post(
            "/api/monitors", json={"name": "ResetMe", "type": "tcp", "target": f"{host}:{port}", "interval_seconds": 60}
        )
    ).json()
    await client.post(f"/api/monitors/{created['id']}/check-now")
    assert len((await client.get(f"/api/monitors/{created['id']}/checks")).json()) == 1

    resp = await client.delete(f"/api/monitors/{created['id']}/history")
    assert resp.status_code == 204

    assert (await client.get(f"/api/monitors/{created['id']}/checks")).json() == []
    assert (await client.get(f"/api/monitors/{created['id']}/incidents")).json() == []
    assert (await client.get(f"/api/monitors/{created['id']}")).status_code == 200


async def test_reset_history_missing_monitor_404(client):
    resp = await client.delete("/api/monitors/999/history")
    assert resp.status_code == 404


async def test_notification_test_endpoint_reports_failure_for_unreachable_target(client):
    created = (
        await client.post(
            "/api/notifications",
            json={"type": "webhook", "name": "x", "config": {"url": "http://127.0.0.1:1/nope"}, "active": True},
        )
    ).json()

    resp = await client.post(f"/api/notifications/{created['id']}/test")
    assert resp.status_code == 200
    assert resp.json() == {"success": False}


async def test_notification_test_missing_channel_404(client):
    resp = await client.post("/api/notifications/999/test")
    assert resp.status_code == 404


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
