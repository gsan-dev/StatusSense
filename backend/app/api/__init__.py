from fastapi import APIRouter

from . import checks, export_import, health_snapshots, incidents, monitors, notifications, status_page, websocket

api_router = APIRouter()
api_router.include_router(monitors.router)
api_router.include_router(checks.router)
api_router.include_router(incidents.router)
api_router.include_router(health_snapshots.router)
api_router.include_router(status_page.router)
api_router.include_router(notifications.router)
api_router.include_router(export_import.router)

ws_router = websocket.router
