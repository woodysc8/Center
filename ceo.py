"""
ceo.py — the master delegator.

Job: look at "new" tasks in the intake table, decide (or confirm) who should
own each one, hand it to the right specialist, and log what happened.

v0 on purpose: no scheduling, no autonomy beyond "run this script." You (or
Copilot, or eventually a cron job / scheduler.py like the one in Sheila's
repo) decide when this runs. Get the delegation logic right before making it
automatic.

Run it directly: `python ceo.py`
"""

from intake import list_tasks, update_status, update_owner
from specialists import richard, juan_whey

SPECIALISTS = {
    "richard": richard.handle_task,
    "juan_whey": juan_whey.handle_task,
}


def review_owner(task: dict) -> str:
    """
    The CEO's chance to override Sheila's initial owner guess. v0 is a
    pass-through (trust Sheila's classification) — this is the natural
    place to add real judgment later: e.g. checking task history, current
    specialist load, or asking an LLM to double-check ambiguous cases.
    """
    return task["owner"]


def run_once() -> list[dict]:
    """Process every 'new' task once. Returns a summary of what happened,
    for logging or for you to eyeball after a run."""
    new_tasks = list_tasks(status="new")
    summary = []

    for task in new_tasks:
        owner = review_owner(task)
        if owner != task["owner"]:
            update_owner(task["id"], owner)

        if owner in SPECIALISTS:
            result = SPECIALISTS[owner](task)
            update_status(task["id"], "in_progress")
            summary.append({"task_id": task["id"], "title": task["title"],
                             "owner": owner, "result": result["result"]})
        elif owner == "samuel":
            # Explicitly needs Samuel's own input — leave it "new" so it
            # surfaces on any dashboard/view_tasks.py run rather than
            # getting silently marked in_progress with nobody working it.
            summary.append({"task_id": task["id"], "title": task["title"],
                             "owner": owner,
                             "result": "Needs Samuel directly — left as 'new'."})
        else:
            # "unassigned" or unrecognized owner — no specialist to hand
            # this to yet (e.g. category "research" before that agent
            # exists). Leave it new rather than guessing.
            summary.append({"task_id": task["id"], "title": task["title"],
                             "owner": owner,
                             "result": "No specialist wired up yet — left as 'new'."})

    return summary


if __name__ == "__main__":
    import json
    results = run_once()
    if not results:
        print("No new tasks.")
    else:
        print(json.dumps(results, indent=2))
