from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import set_redis_pool
from app.core.database import AsyncSessionLocal
from app.api.router import api_router
from app.services.queue_service import restore_queue_from_db

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting QueueCRM API", version="0.1.0")

    # Redis pool
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    set_redis_pool(redis)
    logger.info("Redis connected")

    # Restore queue from DB on startup
    try:
        async with AsyncSessionLocal() as db:
            await restore_queue_from_db(db, redis)
    except Exception as exc:
        logger.warning("Queue restore skipped", reason=str(exc))

    yield

    await redis.aclose()
    logger.info("Shutting down QueueCRM API")


app = FastAPI(
    title="QueueCRM",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
allowed_origins = ["http://localhost:5173", *settings.ALLOWED_ORIGINS]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok", "version": "0.1.0"}
