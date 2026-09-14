"""
delegation.py — Sheila's own delegation logic.

There is no separate "CEO" agent. Sheila IS the orchestrator: she receives
a message from Samuel, decides what it needs, pulls context from Sam 2 when
relevant, delegates to a specialist if one applies, and responds. This
module is the delegation half of that loop — import it directly from
Sheila's own message-handling code (e.g. sheila_handler.py).

Typical usage from Sheila's handler:

    from delegation import handle_message

    def on_message(raw_input: str) -> str:
        outcome = handle_message(raw_input)
        # outcome tells you what happened; Sheila still composes her own
        # reply to Samuel in her own voice — this module doesn't talk to
        # Samuel directly.
        if outcome["owner"] in ("richard", "juan_whey"):
            return f"On it — looping in {outcome['owner']}. {outcome['result']}"
        elif outcome["owner"] == "samuel":
            return "That one's on you — I can't act on it for you."
        else:
            return "Got it, I'll keep this on the list."

Every call still writes a row to the tasks table (via intake.py) — that's
not a separate audit layer someone else reads later, it's just Sheila's own
record-keeping so there's a queryable history/dashboard of what she's
delegated over time.
"""

import re
from importlib import import_module
from typing import Optional

from intake import create_task, update_status
from classifier import classify
import execution
import specialist_delegation


class _LazySpecialistRegistry(dict):
    """Load legacy specialists only when Center actually dispatches to one.

    Calendar capabilities do not use this registry.  Keeping the names in a
    dictionary retains the existing membership and subscription behavior,
    while avoiding an import-time dependency on optional specialist packages
    such as Dee-Klutter.
    """

    _MODULES = {
        "richard": "specialists.richard",
        "juan_whey": "specialists.juan_whey",
        "dee_gmail": "specialists.dee_gmail",
    }

    def __init__(self) -> None:
        super().__init__({name: None for name in self._MODULES})

    def __getitem__(self, owner: str):
        handler = super().__getitem__(owner)
        if handler is None:
            module = import_module(self._MODULES[owner])
            handler = module.handle_task
            super().__setitem__(owner, handler)
        return handler


SPECIALISTS = _LazySpecialistRegistry()


def _error(code: str, message: str) -> dict:
    return {"code": code, "message": message}


def _gmail_request_from_text(raw_input: str) -> Optional[dict]:
    """Turn only clear, read-only Gmail search language into Dee's contract."""
    text = raw_input.strip().lower()
    has_mail_scope = any(term in text for term in ("gmail", "inbox", "mail", "email"))
    has_search_intent = (
        any(term in text for term in ("search", "find", "look through"))
        or ("check" in text and has_mail_scope)
        or "email from" in text
    )
    if not has_mail_scope or not has_search_intent:
        return None

    account = "school" if re.search(r"\bschool\b", text) else "personal"
    if re.search(r"\b(?:inbox|check my inbox)\b", text):
        query = "in:inbox"
    else:
        query = "in:anywhere"

    last_days = re.search(r"\blast\s+(\d+)\s+days?\b", text)
    if last_days:
        query = f"in:anywhere newer_than:{last_days.group(1)}d"
    else:
        sender = re.search(r"\b(?:emails?\s+)?from\s+([\w.+-]+)\b", text)
        if sender:
            query = f"{query} from:{sender.group(1)}"
        else:
            search_terms = re.search(
                r"\b(?:gmail|inbox|mail|emails?)\b\s+(?:for\s+)?(.+)$", text
            )
            if search_terms:
                terms = re.sub(r"^(?:emails?\s+)?(?:about\s+)?", "", search_terms.group(1))
                if terms:
                    query = f"{query} {terms}"

    return {"operation": "search_gmail", "account": account, "query": query}


def _normalize_gmail_metadata(
    raw_input: str,
    context: Optional[dict],
    metadata: Optional[dict],
) -> Optional[dict]:
    """Preserve structured requests; otherwise add a safe search request."""
    if isinstance(metadata, dict) and "gmail_request" in metadata:
        return metadata
    if isinstance(context, dict) and "gmail_request" in context:
        normalized = dict(metadata) if isinstance(metadata, dict) else {}
        normalized["gmail_request"] = context["gmail_request"]
        return normalized

    request = _gmail_request_from_text(raw_input)
    if request is None:
        return metadata
    normalized = dict(metadata) if isinstance(metadata, dict) else {}
    normalized["gmail_request"] = request
    return normalized


def _persistent_task_metadata(metadata: Optional[dict]) -> Optional[dict]:
    """Keep only operation data required to audit or resume legacy work.

    Context is intentionally execution-only: it may contain Sam 2 material,
    profiles, or conversational state that Center must not retain.  Dee's
    normalized Gmail request is the sole current operation-specific item that
    needs to survive in the legacy task ledger.
    """
    if not isinstance(metadata, dict):
        return None
    gmail_request = metadata.get("gmail_request")
    if not isinstance(gmail_request, dict):
        return None
    return {"metadata": {"gmail_request": gmail_request}}


def dispatch_task(task: dict) -> dict:
    """Validate and synchronously dispatch one structured specialist task."""
    if not isinstance(task, dict):
        return {
            "ok": False,
            "owner": None,
            "result": None,
            "error": _error("invalid_task", "task must be an object"),
        }

    owner = task.get("owner")
    if not isinstance(owner, str) or not owner.strip():
        return {
            "ok": False,
            "owner": owner,
            "result": None,
            "error": _error("invalid_task", "task owner is required"),
        }
    if owner not in SPECIALISTS:
        return {
            "ok": False,
            "owner": owner,
            "result": None,
            "error": _error("unknown_specialist", f"no specialist registered for {owner!r}"),
        }

    try:
        result = SPECIALISTS[owner](task)
    except Exception:
        return {
            "ok": False,
            "owner": owner,
            "result": None,
            "error": _error("specialist_error", "specialist failed while handling the task"),
        }

    return {"ok": True, "owner": owner, "result": result, "error": None}


def handle_message(
    raw_input: str,
    *,
    context: Optional[dict] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """
    The one function Sheila calls per incoming message she decides is
    delegation-worthy (not every message needs this — a simple "remind me
    to call Nora" she can just handle herself without going through
    classification/delegation at all).

    Sheila may pass in relevant Sam 2 context and integration metadata here.
    Center treats both as opaque task data and does not retrieve Sam 2
    context itself.

    Returns a dict describing what happened, for Sheila to use when
    composing her own reply. Does not talk to Samuel itself.
    """
    # Sheila's typed execution requests are synchronous, bounded capability
    # calls.  Do not put their authoritative results or injected adapters in
    # the task database.
    if isinstance(metadata, dict) and metadata.get("capability"):
        return execution.execute(raw_input, context, metadata)
    if isinstance(metadata, dict) and metadata.get("specialist"):
        return specialist_delegation.execute({
            "request_id": metadata.get("request_id"),
            "specialist": metadata.get("specialist"),
            "task": raw_input,
            "relevant_context": context,
            "constraints": metadata.get("constraints"),
            "authority_scope": metadata.get("authority_scope"),
        })

    fields = classify(raw_input)
    if fields["owner"] == "dee_gmail":
        metadata = _normalize_gmail_metadata(raw_input, context, metadata)

    task_id = create_task(
        raw_input=raw_input,
        metadata=_persistent_task_metadata(metadata),
        **fields,
    )

    owner = fields["owner"]
    task = {
        **fields,
        "id": task_id,
        "raw_input": raw_input,
        "context": context,
        "metadata": metadata,
    }

    if owner in SPECIALISTS:
        update_status(task_id, "in_progress")
        dispatch = dispatch_task(task)
        if not dispatch["ok"]:
            update_status(task_id, "dropped")
            return {
                "task_id": task_id,
                "owner": owner,
                "category": fields["category"],
                "result": None,
                "error": dispatch["error"],
                "status": "dropped",
            }
        result = dispatch["result"]
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        update_status(task_id, "done")
        return {
            "task_id": task_id,
            "owner": owner,
            "category": fields["category"],
            "result": result,
            "status": "done",
        }

    if owner == "samuel":
        # Needs Samuel's own input — nothing to delegate to.
        return {
            "task_id": task_id,
            "owner": owner,
            "category": fields["category"],
            "result": "Needs Samuel directly.",
            "status": "new",
        }

    # "unassigned" or a category with no specialist yet (e.g. research,
    # before that agent exists). Leave it queued rather than guessing.
    return {
        "task_id": task_id,
        "owner": owner,
        "category": fields["category"],
        "result": "No specialist available yet — queued.",
        "status": "new",
    }


def sweep_unassigned() -> list[dict]:
    """
    Optional utility, not part of the per-message flow: re-check tasks that
    were left 'new' because no specialist existed at the time (e.g. research
    tasks before a researcher agent is built). Run this manually whenever a
    new specialist comes online, to retroactively process anything queued
    for it. Not scheduled/automatic — cost-consciousness means nothing here
    runs on its own.
    """
    from intake import list_tasks

    results = []
    for task in list_tasks(status="new"):
        owner = task["owner"]
        if owner in SPECIALISTS:
            update_status(task["id"], "in_progress")
            dispatch = dispatch_task(task)
            if dispatch["ok"]:
                update_status(task["id"], "done")
                result = dispatch["result"]
                if isinstance(result, dict) and "result" in result:
                    result = result["result"]
                results.append({"task_id": task["id"], "title": task["title"],
                                "owner": owner, "result": result})
            else:
                update_status(task["id"], "dropped")
                results.append({"task_id": task["id"], "title": task["title"],
                                "owner": owner, "result": None,
                                "error": dispatch["error"]})
    return results


if __name__ == "__main__":
    import json
    for example in [
        "Should I bump my Roth contributions before year-end?",
        "Find me flights to Lisbon in October",
        "What's the latest on fintech PR trends?",
    ]:
        outcome = handle_message(example)
        print(example, "->", json.dumps(outcome))
