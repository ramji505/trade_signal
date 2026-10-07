from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.api.health import router as health_router
from app.api.market import router as market_router
from app.api.signals import router as signals_router
from app.api.performance import router as performance_router
from app.api.backtest import router as backtest_router
from app.api.execution import router as execution_router
from app.websocket.manager import ws_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} in {settings.ENVIRONMENT} mode.")
    from app.services.live_scanner import live_market_scanner
    if settings.UPSTOX_ACCESS_TOKEN:
        await live_market_scanner.start()
        logger.info("Live Market Background Scanner started successfully.")
    yield
    if settings.UPSTOX_ACCESS_TOKEN:
        await live_market_scanner.stop()
    logger.info(f"Shutting down {settings.APP_NAME}.")



app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Private NIFTY 50 Intraday Trading Signal System (Signal-Only Architecture)",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS to accept local and AWS EC2 requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health_router)
app.include_router(market_router)
app.include_router(signals_router)
app.include_router(performance_router)
app.include_router(backtest_router)
app.include_router(execution_router)


@app.get("/", summary="Root API Information")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "ONLINE",
        "mode": "SIGNAL_ONLY",
        "docs_url": "/docs"
    }


@app.get("/api/status", summary="Frontend Compatibility Status Endpoint")
async def api_status():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "mode": "SIGNAL_ONLY",
        "order_execution": False,
        "disclaimer": settings.DISCLAIMER
    }


@app.get("/api/signals", summary="Frontend Compatibility Signals Endpoint")
async def api_signals():
    from app.api.signals import get_current_signal
    return await get_current_signal()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and receive client messages
            data = await websocket.receive_text()
            # Echo or handle incoming subscriptions
            await websocket.send_json({"type": "ACK", "payload": data})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket exception: {e}")
        ws_manager.disconnect(websocket)
