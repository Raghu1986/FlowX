import logging
import time
import socket
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.routers import audit, ingest, ws, ws_health, admin_logs, logs_today, logs_tail, auth, user_api, client_api
from app.core.redis_client import RedisClient
from app.core.config import settings
from app.core.db import init_db, close_db
from app.core.logging import setup_logging
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.token_cache_middleware import TokenCacheMiddleware
from app.core.heartbeat import emit_heartbeat
from app.core.token_cache import TokenCache

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    app.state.logger = logging.getLogger("FLOWX")
    logger = app.state.logger

    app_info = {
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "hostname": socket.gethostname(),
    }

    start_total = time.perf_counter()
    logger.info("🚀 Application startup initiated", extra={"event": "startup_begin", **app_info})

    # --- INIT DB ---
    await init_db()
    logger.info("✅ Database initialized", extra={"event": "db_init", **app_info})

    # --- INIT REDIS ---
    redis = RedisClient(settings.REDIS_URL)
    await redis.connect()
    app.state.redis = redis
    logger.info("✅ Redis connected", extra={"event": "redis_connect", **app_info})

    # --- Emit first heartbeat ---
    try:
        await emit_heartbeat(app.state.redis, logger)
    except Exception as e:
        logger.exception("❌ Failed to emit startup heartbeat", extra={"error": str(e)})

    total_elapsed = round((time.perf_counter() - start_total) * 1000, 2)
    logger.info("🟢 Application startup complete", extra={"event": "startup_complete", "elapsed_ms": total_elapsed, **app_info})

    # --- Background periodic heartbeat ---
    async def periodic_heartbeat():
        while settings.HEARTBEAT_ENABLED:
            await asyncio.sleep(300)  # every 5 minutes
            try:
                await emit_heartbeat(app.state.redis, logger)
            except Exception as e:
                logger.error("❌ Periodic heartbeat failed", extra={"error": str(e)})

    heartbeat_task = asyncio.create_task(periodic_heartbeat())

    app.state.token_cache = TokenCache(redis_url=settings.REDIS_URL)

    yield

    heartbeat_task.cancel()

    # --- SHUTDOWN ---
    logger.info("🔻 Application shutdown initiated", extra={"event": "shutdown_begin", **app_info})
    await close_db()
    await app.state.redis.close()
    logger.info("👋 Application shutdown complete", extra={"event": "shutdown_complete", **app_info})


app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION, lifespan=lifespan)
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(TokenCacheMiddleware)

app.include_router(audit.router)
app.include_router(ingest.router)
app.include_router(ws.router)
app.include_router(ws_health.router)
app.include_router(admin_logs.router)
app.include_router(logs_today.router)
app.include_router(logs_tail.router)
app.include_router(auth.router)
app.include_router(user_api.router)
app.include_router(client_api.router)


@app.get("/")
async def ping(request: Request):
    logger = request.app.state.logger
    logger.info("👋 Ping request received", extra={"event": "ping_request", "env": settings.APP_ENV})
    return JSONResponse({"status": "ok", "env": settings.APP_ENV, "version": settings.APP_VERSION})
