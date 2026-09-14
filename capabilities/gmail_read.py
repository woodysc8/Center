"""Non-persistent read-only Gmail capability through an injected Dee adapter."""

from __future__ import annotations

from typing import Any


_OPERATIONS = {"search_gmail", "get_message", "get_thread"}


def _failure(request_id: str, message: str) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "status": "failed",
        "result": None,
        "authoritative_source": "dee_klutter",
        "side_effects": [],
        "errors": [message],
        "durable_memory_candidate": None,
    }


def _validate_request(value: object) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(value, dict):
        return None, "gmail_read requires a Gmail request object."
    operation = value.get("operation")
    account = value.get("account")
    if operation not in _OPERATIONS:
        return None, "gmail_read requires a supported Gmail operation."
    if not isinstance(account, str) or not account.strip():
        return None, "gmail_read requires an account."
    required_field = {
        "search_gmail": "query",
        "get_message": "message_id",
        "get_thread": "thread_id",
    }[operation]
    if not isinstance(value.get(required_field), str) or not value[required_field].strip():
        return None, f"gmail_read requires {required_field}."
    return value, None


def execute(request: dict[str, Any], dependencies: dict[str, Any]) -> dict[str, Any]:
    """Execute one Dee-Klutter read request without owning Gmail access."""
    request_id = str(request.get("request_id", ""))
    if request.get("authority_scope") != "read":
        return _failure(request_id, "gmail_read accepts read authority only.")
    gmail_request, error = _validate_request(request.get("capability_input"))
    if error:
        return _failure(request_id, error)
    reader = dependencies.get("gmail_reader") if isinstance(dependencies, dict) else None
    if not callable(reader):
        return _failure(request_id, "gmail_read requires an injected Dee Gmail reader.")
    try:
        dee_result = reader({"metadata": {"gmail_request": gmail_request}})
    except Exception:
        return _failure(request_id, "Dee-Klutter could not read Gmail.")
    if not isinstance(dee_result, dict) or dee_result.get("ok") is not True:
        error_value = dee_result.get("error") if isinstance(dee_result, dict) else None
        message = error_value.get("message") if isinstance(error_value, dict) else None
        return _failure(request_id, message or "Dee-Klutter could not read Gmail.")
    return {
        "request_id": request_id,
        "status": "succeeded",
        "result": dee_result,
        "authoritative_source": "dee_klutter",
        "side_effects": [],
        "errors": [],
        "durable_memory_candidate": None,
    }
