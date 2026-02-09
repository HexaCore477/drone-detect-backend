"""Config service - SQLite database for application configuration."""
import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Database file path: backend/app/config.db
_DB_PATH = Path(__file__).resolve().parent.parent / "config.db"
_CONNECTION: Optional[sqlite3.Connection] = None


def _get_connection() -> sqlite3.Connection:
    """Get or create SQLite connection. Thread-safe for FastAPI (single-threaded per request)."""
    global _CONNECTION
    if _CONNECTION is None:
        _CONNECTION = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _CONNECTION.row_factory = sqlite3.Row
        _init_db()
    return _CONNECTION


def _init_db() -> None:
    """Initialize database schema if not exists."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    
    # Insert default value if not exists
    cursor.execute("""
        INSERT OR IGNORE INTO config (key, value) 
        VALUES ('is_auto_tracking', 'false')
    """)
    
    conn.commit()
    logger.info("Config database initialized: %s", _DB_PATH)


def get_auto_tracking() -> bool:
    """Get is_auto_tracking config value. Returns False if not set."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM config WHERE key = 'is_auto_tracking'")
    row = cursor.fetchone()
    if row is None:
        return False
    return row["value"].lower() == "true"


def set_auto_tracking(value: bool) -> None:
    """Set is_auto_tracking config value."""
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO config (key, value) 
        VALUES ('is_auto_tracking', ?)
        ON CONFLICT(key) DO UPDATE SET value = ?
    """, (str(value).lower(), str(value).lower()))
    conn.commit()
    logger.info("Config updated: is_auto_tracking = %s", value)
