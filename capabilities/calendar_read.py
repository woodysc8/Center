"""Non-persistent read-only Calendar capability for Center."""

from __future__ import annotations

from datetime import datetime, time, timedelta
import logging
from time import monotonic
from typing import Any, Callable
from zoneinfo import ZoneInfo


logger = logging.getLogger(__name__)
CalendarReader = Callable[[datetime, datetime], list[dict[str, Any]]]


def _failure(request_id: str, message: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "status": "failed",
        "result": None,
        "authoritative_source": "google_calendar",
        "side_effects": [],
        "errors": [message],
        "durable_memory_candidate": None,
    }


def execute(request: dict[str, Any], reader: CalendarReader) -> dict[str, Any]:
    """Read tomorrow's events through an injected authoritative adapter.

    Center deliberately receives a callable boundary instead of OAuth
    credentials or a calendar database.  The host owns authentication.
    """
    request_id = str(request.get("request_id", ""))
    started = monotonic()
    logger.info("capability_started request_id=%s capability=calendar_read", request_id)
    try:
        if not callable(reader):
            raise ValueError("calendar_read requires an internal calendar reader")
        zone = ZoneInfo("America/New_York")
        today = datetime.now(zone).date()
        start = datetime.combine(today + timedelta(days=1), time.min, tzinfo=zone)
        end = start + timedelta(days=1)
        events = reader(start, end)
        if not isinstance(events, list):
            raise ValueError("calendar reader returned an invalid event collection")
    except Exception:
        duration_ms = round((monotonic() - started) * 1000)
        logger.warning("capability_failed request_id=%s capability=calendar_read status=failed duration_ms=%s", request_id, duration_ms)
        return _failure(request_id, "Google Calendar could not be read.")
    duration_ms = round((monotonic() - started) * 1000)
    logger.info("capability_completed request_id=%s capability=calendar_read status=succeeded duration_ms=%s", request_id, duration_ms)
    return {
        "request_id": request_id,
        "status": "succeeded",
        "result": {"events": events, "count": len(events)},
        "authoritative_source": "google_calendar",
        "side_effects": [],
        "errors": [],
        "durable_memory_candidate": None,
    }
