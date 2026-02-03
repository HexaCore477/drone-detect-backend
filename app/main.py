"""FastAPI application factory and configuration."""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import camera, stream
from app.core.config import get_settings

# Mitigate FFmpeg threading issues with RTSP
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|threads;1"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Drone Detection API",
        description="Hikvision camera streaming and drone detection",
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

    @app.get("/")
    def root():
        return {
            "message": "Drone Detection API",
            "stream": "/api/stream",
        }

    return app


app = create_app()
