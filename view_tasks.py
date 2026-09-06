"""
view_tasks.py — quick manual look at the task queue.

Run: python view_tasks.py [status]
e.g. python view_tasks.py new
     python view_tasks.py         (shows everything)

This is a placeholder for the "first real company dashboard" mentioned in
task_intake_spec.md — fine as a CLI until it's worth a real UI.
"""

import sys
from intake import list_tasks

STATUS_ICON = {"new": "🆕", "in_progress": "⏳", "done": "✅", "dropped": "🗑️"}


def main():
    status_filter = sys.argv[1] if len(sys.argv) > 1 else None
    tasks = list_tasks(status=status_filter)

    if not tasks:
        print("No tasks found." + (f" (status={status_filter})" if status_filter else ""))
        return

    for t in tasks:
        icon = STATUS_ICON.get(t["status"], "•")
        print(f"{icon} [{t['priority']:>6}] {t['title']}")
        print(f"     owner={t['owner']}  category={t['category']}  status={t['status']}")
        print(f"     created={t['created_at']}")
        print()


if __name__ == "__main__":
    main()
