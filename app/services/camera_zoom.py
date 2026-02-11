"""Hikvision PTZ zoom control via ISAPI (PUT /ISAPI/PTZCtrl/channels/1/continuous)."""
import logging
from typing import Optional
from urllib.parse import urlparse

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Default HTTP port for Hikvision ISAPI (optional override via CAMERA_HTTP_PORT)
DEFAULT_HTTP_PORT = 80

# PTZ channel (1 for main stream)
PTZ_CHANNEL = 1


def _parse_rtsp_credentials(rtsp_url: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse RTSP URL to get hostname, username, password. Returns (host, user, pass)."""
    try:
        u = urlparse(rtsp_url)
        host = u.hostname
        user = u.username
        password = u.password
        if not host:
            return None, None, None
        return host, user, password
    except Exception as e:
        logger.warning("Failed to parse RTSP URL for zoom: %s", e)
        return None, None, None


def _get_camera_http_base() -> Optional[str]:
    """Build HTTP base URL for camera ISAPI (e.g. http://192.168.1.64:80)."""
    import os

    settings = get_settings()
    host, _, _ = _parse_rtsp_credentials(settings.rtsp_url)
    if not host:
        return None
    port = int(os.getenv("CAMERA_HTTP_PORT", str(DEFAULT_HTTP_PORT)))
    return f"http://{host}:{port}"


def _get_camera_auth() -> tuple[Optional[str], Optional[str]]:
    """Return (username, password) for camera ISAPI from RTSP URL or env."""
    import os

    settings = get_settings()
    _, user, password = _parse_rtsp_credentials(settings.rtsp_url)
    if user is None:
        user = os.getenv("CAMERA_HTTP_USER", "")
    if password is None:
        password = os.getenv("CAMERA_HTTP_PASSWORD", "")
    return user or None, password or None


def _ptz_continuous(pan: int = 0, tilt: int = 0, zoom: int = 0) -> tuple[bool, str]:
    """
    Send PTZ continuous move command to Hikvision camera via ISAPI.
    PUT /ISAPI/PTZCtrl/channels/1/continuous with XML body.
    pan/tilt/zoom: -1 = left/down/out, 0 = stop, 1 = right/up/in.
    Returns (success, message).
    """
    try:
        import requests
        from requests.auth import HTTPDigestAuth
    except ImportError:
        logger.error("requests library required for camera zoom (pip install requests)")
        return False, "requests not installed"

    base = _get_camera_http_base()
    user, password = _get_camera_auth()
    if not base:
        return False, "Camera host unknown (check RTSP_URL)"
    if not user or not password:
        return False, "Camera credentials unknown (check RTSP_URL or CAMERA_HTTP_USER/PASSWORD)"

    url = f"{base}/ISAPI/PTZCtrl/channels/{PTZ_CHANNEL}/continuous"
    # Hikvision ISAPI PTZData: pan, tilt, zoom in range typically -1, 0, 1 (continuous)
    xml_body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<PTZData version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">\n'
        f"  <pan>{pan}</pan>\n"
        f"  <tilt>{tilt}</tilt>\n"
        f"  <zoom>{zoom}</zoom>\n"
        "</PTZData>"
    )
    headers = {"Content-Type": "application/xml"}

    try:
        r = requests.put(
            url,
            data=xml_body,
            headers=headers,
            auth=HTTPDigestAuth(user, password),
            timeout=5,
        )
        if r.status_code == 200:
            return True, "OK"
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except requests.exceptions.Timeout:
        logger.warning("Camera zoom request timeout: %s", url)
        return False, "Request timeout"
    except requests.exceptions.RequestException as e:
        logger.warning("Camera zoom request failed: %s", e)
        return False, str(e)


def zoom_connect() -> tuple[bool, str]:
    """
    Test connection to camera for zoom control (e.g. send stop command to verify ISAPI works).
    Returns (success, message).
    """
    success, msg = _ptz_continuous(pan=0, tilt=0, zoom=0)
    if success:
        return True, "Camera zoom control connected"
    return False, msg


def zoom_in() -> tuple[bool, str]:
    """Start zoom in (continuous). Send zoom=1. Call zoom_stop to stop."""
    return _ptz_continuous(pan=0, tilt=0, zoom=1)


def zoom_out() -> tuple[bool, str]:
    """Start zoom out (continuous). Send zoom=-1. Call zoom_stop to stop."""
    return _ptz_continuous(pan=0, tilt=0, zoom=-1)


def zoom_stop() -> tuple[bool, str]:
    """Stop PTZ movement (zoom and pan/tilt). Send zoom=0, pan=0, tilt=0."""
    return _ptz_continuous(pan=0, tilt=0, zoom=0)
