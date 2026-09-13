from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import api_router, ws_router
from .database import close_db, init_db
from .scheduler import load_all_monitors, scheduler

logging.basicConfig(level=logging.INFO)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler.start()
    await load_all_monitors()
    yield
    scheduler.shutdown(wait=False)
    await close_db()


app = FastAPI(
    title="StatusSense",
    description="Monitorizacion de servicios con deteccion predictiva de degradacion.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)
app.include_router(ws_router)

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
