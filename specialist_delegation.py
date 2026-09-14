"""Non-persistent structured delegation to explicitly registered specialists."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


SpecialistAdapter = Callable[[dict[str, Any]], dict[str, Any]]
_VALID_AUTHORITY_SCOPES = {"read", "write"}


def _juan_whey_stub(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "specialist": request["specialist"],
        "boundary_reached": True,
        "external_action_performed": False,
        "message": "Juan Whey delegation boundary reached; no external action was performed.",
    }


def _richard_stub(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "specialist": request["specialist"],
        "boundary_reached": True,
        "external_action_performed": False,
        "message": "Richard delegation boundary reached; no external action was performed.",
    }


_SPECIALISTS: dict[str, SpecialistAdapter] = {
    "juan_whey": _juan_whey_stub,
    "richard": _richard_stub,
}


def get_specialist(name: str) -> SpecialistAdapter | None:
    """Resolve a fixed structured-specialist adapter without discovery."""
    return _SPECIALISTS.get(name)


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


def execute(request: object) -> dict[str, Any]:
    """Validate and execute a Sheila-selected structured specialist request."""
    if not isinstance(request, dict):
        return _failure("", "SpecialistDelegationRequest must be an object.")
    request_id = request.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        return _failure("", "SpecialistDelegationRequest requires request_id.")
    specialist = request.get("specialist")
    if not isinstance(specialist, str) or not specialist.strip():
        return _failure(request_id, "SpecialistDelegationRequest requires specialist.")
    task = request.get("task")
    if not isinstance(task, str) or not task.strip():
        return _failure(request_id, "SpecialistDelegationRequest requires task.")
    context = request.get("relevant_context", {})
    if context is None:
        context = {}
    if not isinstance(context, dict):
        return _failure(request_id, "SpecialistDelegationRequest relevant_context must be an object.")
    constraints = request.get("constraints", [])
    if constraints is None:
        constraints = []
    if not isinstance(constraints, list):
        return _failure(request_id, "SpecialistDelegationRequest constraints must be a list.")
    authority_scope = request.get("authority_scope")
    if not isinstance(authority_scope, str) or authority_scope not in _VALID_AUTHORITY_SCOPES:
        return _failure(request_id, "SpecialistDelegationRequest requires a valid authority_scope.")
    adapter = get_specialist(specialist)
    if adapter is None:
        return _failure(request_id, f"Unsupported specialist: {specialist}.")
    source = f"specialist_boundary:{specialist}"
    if authority_scope != "read":
        return _failure(request_id, f"{specialist} supports read authority only.", source=source)

    adapter_request = {
        "request_id": request_id,
        "specialist": specialist,
        "task": task,
        "relevant_context": context,
        "constraints": constraints,
        "authority_scope": authority_scope,
    }
    try:
        result = adapter(adapter_request)
    except Exception:
        return _failure(request_id, f"{specialist} could not execute the delegation request.", source=source)
    if not isinstance(result, dict):
        return _failure(request_id, f"{specialist} returned an invalid delegation result.", source=source)
    return {
        "request_id": request_id,
        "status": "succeeded",
        "result": result,
        "authoritative_source": source,
        "side_effects": [],
        "errors": [],
        "durable_memory_candidate": None,
    }
