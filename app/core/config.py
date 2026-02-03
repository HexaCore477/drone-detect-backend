"""Application configuration."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment."""

    rtsp_url: str
    cors_origins: list[str]


def get_settings() -> Settings:
    """Load and return application settings."""
    rtsp_url = os.getenv(
        "RTSP_URL",
        "rtsp://admin:nanjing12345@192.168.1.64:554/Streaming/Channels/101",
    )
    cors_raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8080,http://localhost:5173,http://localhost:3000",
    )
    cors_origins = [o.strip() for o in cors_raw.split(",") if o.strip()]
    return Settings(rtsp_url=rtsp_url, cors_origins=cors_origins)
