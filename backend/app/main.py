"""FastAPI application factory and configuration."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import camera, config, ptu, stream, tracking, view_subscription
from app.core.config import get_settings
from app.services import config as config_service, joystick as joystick_service
from app.services import ptu as ptu_service
from app.services import tracking_pipeline

# CRITICAL: Disable all FFmpeg buffering and force UDP
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|fflags;nobuffer|flags;low_delay|strict;experimental"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start async pipeline: Thread 1 (capture), Thread 2 (detection), Thread 3 (PTU control)
    tracking_pipeline.start_pipeline()
    # Start joystick control thread (active when auto-tracking is off)
    joystick_service.start_joystick()
    yield
    # On shutdown, stop pipeline, joystick, and disconnect PTU
    tracking_pipeline.stop_pipeline()
    joystick_service.stop_joystick()
    ptu_service.disconnect()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Drone Detection API",
        description="Hikvision camera streaming and drone detection",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(stream.router, prefix="/api")
    app.include_router(camera.router, prefix="/api")
    app.include_router(ptu.router, prefix="/api")
    app.include_router(tracking.router, prefix="/api")
    app.include_router(config.router, prefix="/api")
    app.include_router(view_subscription.router, prefix="/api")

    @app.get("/")
    def root():
        return {
            "message": "Drone Detection API",
            "stream": "/api/stream",
        }

    return app


app = create_app()
