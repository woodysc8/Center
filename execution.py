"""Structured execution-request dispatch for Center's internal capabilities."""

from __future__ import annotations

import logging
from time import monotonic
from typing import Any

from capabilities import calendar_read


logger = logging.getLogger(__name__)


def _failure(request_id: str, message: str, *, source: str = "center") -> dict[str, Any]:
    return {
        "request_id": request_id,
        "status": "failed",
        "result": None,
        "authoritative_source": source,
        "side_effects": [],
        "errors": [message],
        "durable_memory_candidate": None,
    }


def execute(raw_input: str, context: dict | None, metadata: dict | None) -> dict[str, Any]:
    """Validate and dispatch Sheila's bounded ExecutionRequest mapping.

    Structured execution is intentionally non-persistent: task history is for
    delegated specialist work, not a shadow of Calendar data or Sam 2.
    """
    started = monotonic()
    metadata = metadata if isinstance(metadata, dict) else {}
    request_id = metadata.get("request_id")
    capability = metadata.get("capability")
    if not isinstance(request_id, str) or not request_id.strip():
        return _failure("", "ExecutionRequest requires request_id.")
    if not isinstance(capability, str) or not capability.strip():
        return _failure(request_id, "ExecutionRequest requires capability.")
    if not isinstance(raw_input, str) or not raw_input.strip():
        return _failure(request_id, "ExecutionRequest requires task text.")
    if context is not None and not isinstance(context, dict):
        return _failure(request_id, "ExecutionRequest relevant_context must be an object.")
    if metadata.get("authority_scope", "read") != "read":
        return _failure(request_id, "calendar_read accepts read authority only.")

    logger.info("center_request_received request_id=%s capability=%s", request_id, capability)
    if capability != "calendar_read":
        logger.info("capability_selected request_id=%s capability=%s status=unsupported", request_id, capability)
        return _failure(request_id, f"Unsupported capability: {capability}.")
    logger.info("capability_selected request_id=%s capability=calendar_read", request_id)
    result = calendar_read.execute(
        {"request_id": request_id, "task": raw_input, "relevant_context": context or {}, "constraints": metadata.get("constraints", [])},
        metadata.get("calendar_reader"),
    )
    logger.info("center_execution_result request_id=%s capability=%s status=%s duration_ms=%s", request_id, capability, result["status"], round((monotonic() - started) * 1000))
    return result
