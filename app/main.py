"""
Bio-Dashboard FastAPI Application.
Entrypoint for the API server.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import HA_POLL_INTERVAL_SEC, HA_TOKEN
from app.core.database import init_db
from app.core.ha_importer import poll_and_store
from app.api.routes import router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("bio.main")

scheduler = AsyncIOScheduler(timezone="Europe/Zurich")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Init database
    init_db()
    log.info("Bio-Dashboard API starting")

    # Start HA polling scheduler
    ha_configured = HA_TOKEN and "PASTE" not in HA_TOKEN and len(HA_TOKEN) > 20
    if ha_configured:
        scheduler.add_job(
            poll_and_store,
            "interval",
            seconds=HA_POLL_INTERVAL_SEC,
            id="ha_poll",
            replace_existing=True,
        )
        scheduler.start()
        log.info("HA poller scheduled every %d seconds", HA_POLL_INTERVAL_SEC)

        # Run one initial poll
        asyncio.create_task(poll_and_store())
    else:
        log.info("HA not configured -- running standalone (no health import)")

    yield

    # Shutdown
    if scheduler.running:
        scheduler.shutdown(wait=False)
    log.info("Bio-Dashboard API stopped")


app = FastAPI(
    title="Bio-Dashboard API",
    version="1.0.0",
    description="Quantified Self API -- Leandro Edition",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {"service": "bio-dashboard", "docs": "/docs"}
