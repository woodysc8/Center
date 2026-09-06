"""
juan_whey.py — interface stub for Juan Whey (the travel agent).

Same contract as richard.py: handle_task(task: dict) -> dict.
Replace once there's a real way to reach Juan Whey's ChatGPT setup
(most travel APIs are dev-only, per earlier conversation — this may end up
needing a browser-automation or manual-handoff approach rather than a clean
API call, worth deciding deliberately rather than defaulting to one).
"""


def handle_task(task: dict) -> dict:
    print(f"[juan_whey] received task: {task['title']}")
    print(f"[juan_whey] brief: {task['brief']}")
    # TODO(copilot): replace with a real call/handoff to Juan Whey.
    return {
        "result": "Juan Whey stub: task logged, no real action taken yet.",
        "handled_by": "juan_whey_stub",
    }
