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

from typing import Optional

from intake import create_task, update_status
from classifier import classify
from specialists import dee_gmail, richard, juan_whey

SPECIALISTS = {
    "richard": richard.handle_task,
    "juan_whey": juan_whey.handle_task,
    "dee_gmail": dee_gmail.handle_task,
}


def _error(code: str, message: str) -> dict:
    return {"code": code, "message": message}


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
    task_metadata = {}
    if context is not None:
        task_metadata["context"] = context
    if metadata is not None:
        task_metadata["metadata"] = metadata

    fields = classify(raw_input)
    task_id = create_task(
        raw_input=raw_input,
        metadata=task_metadata or None,
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
        dispatch = dispatch_task(task)
        update_status(task_id, "in_progress")
        if not dispatch["ok"]:
            return {
                "task_id": task_id,
                "owner": owner,
                "category": fields["category"],
                "result": None,
                "error": dispatch["error"],
                "status": "in_progress",
            }
        result = dispatch["result"]
        if isinstance(result, dict) and "result" in result:
            result = result["result"]
        return {
            "task_id": task_id,
            "owner": owner,
            "category": fields["category"],
            "result": result,
            "status": "in_progress",
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
            result = SPECIALISTS[owner](task)
            update_status(task["id"], "in_progress")
            results.append({"task_id": task["id"], "title": task["title"],
                             "owner": owner, "result": result["result"]})
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
