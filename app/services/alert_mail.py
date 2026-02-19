"""Alert email service — sends balloon detection alerts via Resend API.

Sends an alert when the total balloon count changes. Drift avoidance:
- New count must be stable for 5 consecutive frames
- 60 second cooldown between alerts
- 1 second minimum gap for Resend API rate limit (2 req/sec)
"""
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

STABILITY_COUNT = 20
ALERT_COOLDOWN_SEC = 60.0
RESEND_MIN_GAP_SEC = 1.0

_prev_count: int = -1
_consecutive_same: int = 0
_last_alerted_count: int = -1
_last_send_time: float = 0.0

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_NAMED_RE = re.compile(r"^.+<\s*([^\s@]+@[^\s@]+\.[^\s@]+)\s*>$")


def _valid_email(addr: str) -> bool:
    s = addr.strip().strip('"\'')
    return bool(s) and (_EMAIL_RE.match(s) or _NAMED_RE.match(s))


def _parse_recipients(raw: str) -> List[str]:
    parts = [p.strip().strip('"\'') for p in raw.split(",") if p.strip()]
    valid = [p for p in parts if _valid_email(p)]
    invalid = [p for p in parts if p and not _valid_email(p)]
    if invalid:
        logger.warning("Invalid ALERT_MAIL_TO (skipped): %s", invalid)
    return valid


def _send(timestamp: float, count: int) -> bool:
    api_key = os.getenv("RESEND_API_KEY")
    to_raw = os.getenv("ALERT_MAIL_TO", "")
    from_addr = os.getenv("ALERT_MAIL_FROM", "alerts@resend.dev")

    if not api_key:
        logger.warning("RESEND_API_KEY not set, skipping alert")
        return False
    recipients = _parse_recipients(to_raw)
    if not recipients:
        logger.warning("No valid ALERT_MAIL_TO addresses")
        return False

    try:
        import resend

        resend.api_key = api_key
        ts_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Balloon Detection Alert</title></head>
<body>
  <h2>Balloon Detection Alert</h2>
  <p><strong>Timestamp:</strong> {ts_str}</p>
  <p><strong>Total balloons:</strong> {count}</p>
</body>
</html>
"""
        resend.Emails.send({
            "from": from_addr,
            "to": recipients,
            "subject": f"Balloon Detection Alert - {ts_str}",
            "html": html,
        })
        logger.info("Alert email sent: %d balloons", count)
        return True
    except ImportError:
        logger.warning("resend package not installed")
        return False
    except Exception as e:
        logger.error("Alert email failed: %s", e, exc_info=True)
        return False


def process_balloon_detection(timestamp: float, track_items: List[Dict[str, Any]]) -> None:
    """Process detection state. Send alert when total count changes and is stable."""
    global _prev_count, _consecutive_same, _last_alerted_count, _last_send_time

    count = len(track_items) if track_items else 0

    if count == _prev_count:
        _consecutive_same += 1
        now = time.monotonic()
        gap = now - _last_send_time
        if (
            _consecutive_same >= STABILITY_COUNT
            and count != _last_alerted_count
            and gap >= ALERT_COOLDOWN_SEC
            and gap >= RESEND_MIN_GAP_SEC
        ):
            _last_send_time = now
            if _send(timestamp, count):
                _last_alerted_count = count
    else:
        _prev_count = count
        _consecutive_same = 1
