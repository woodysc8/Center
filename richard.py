"""
richard.py — interface stub for Richard Newport (the finance/CPA agent).

Currently: does nothing real, just logs and returns a canned acknowledgment.
This is the exact seam to replace once you decide how the CEO actually
reaches Richard — a direct API call to wherever he's hosted, a webhook, etc.

Contract: handle_task(task: dict) -> dict
    Input is a row from intake.list_tasks() (a dict with the task schema
    fields). Output should be a dict with at least a "result" string —
    the CEO doesn't care about anything beyond that contract, so the real
    implementation can return richer detail if useful later.
"""


def handle_task(task: dict) -> dict:
    print(f"[richard] received task: {task['title']}")
    print(f"[richard] brief: {task['brief']}")
    # TODO(copilot): replace with a real call to Richard's actual backend.
    # Until Richard has a stable API, this just simulates receipt.
    return {
        "result": "Richard stub: task logged, no real action taken yet.",
        "handled_by": "richard_stub",
    }
