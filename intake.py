"""
intake.py — shared task-intake layer for the personal AI network.

Creates the `tasks` table and exposes create_task()/list_tasks()/update_status().
This is the seam every agent (Sheila, the CEO, eventually Richard and Juan
Whey) reads from or writes to, instead of a bespoke integration per pair.

Sheila calls create_task() silently when she decides a message is
delegation-worthy — she still replies to Samuel normally in the same turn.
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List

from config import DB_PATH

VALID_CATEGORIES = {"finance", "travel", "research", "reminder", "unsure"}
VALID_OWNERS = {"richard", "juan_whey", "dee_gmail", "sheila", "samuel", "unassigned"}
VALID_PRIORITIES = {"low", "normal", "high"}
VALID_STATUSES = {"new", "in_progress", "done", "dropped"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'sheila',
    raw_input TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    brief TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'normal',
    status TEXT NOT NULL DEFAULT 'new',
    owner TEXT NOT NULL DEFAULT 'unassigned',
    deadline TEXT,
    metadata TEXT
);
"""


def _connect():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(SCHEMA)
    return conn


def create_task(
    raw_input: str,
    category: str,
    title: str,
    brief: str,
    owner: str = "unassigned",
    priority: str = "normal",
    deadline: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> str:
    """Write a new task row. Returns the generated task id."""
    if category not in VALID_CATEGORIES:
        raise ValueError(f"category must be one of {VALID_CATEGORIES}, got {category!r}")
    if owner not in VALID_OWNERS:
        raise ValueError(f"owner must be one of {VALID_OWNERS}, got {owner!r}")
    if priority not in VALID_PRIORITIES:
        raise ValueError(f"priority must be one of {VALID_PRIORITIES}, got {priority!r}")

    task_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO tasks
                (id, created_at, source, raw_input, category, title, brief,
                 priority, status, owner, deadline, metadata)
            VALUES (?, ?, 'sheila', ?, ?, ?, ?, ?, 'new', ?, ?, ?)
            """,
            (
                task_id,
                created_at,
                raw_input,
                category,
                title,
                brief,
                priority,
                owner,
                deadline,
                json.dumps(metadata) if metadata else None,
            ),
        )
    return task_id


def list_tasks(status: Optional[str] = None, owner: Optional[str] = None) -> List[dict]:
    """Read tasks back, optionally filtered."""
    query = "SELECT * FROM tasks"
    clauses, params = [], []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if owner:
        clauses.append("owner = ?")
        params.append(owner)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC"

    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def update_status(task_id: str, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}, got {status!r}")
    with _connect() as conn:
        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (status, task_id))


def update_owner(task_id: str, owner: str) -> None:
    """Used by the CEO when it overrides Sheila's initial owner guess."""
    if owner not in VALID_OWNERS:
        raise ValueError(f"owner must be one of {VALID_OWNERS}, got {owner!r}")
    with _connect() as conn:
        conn.execute("UPDATE tasks SET owner = ? WHERE id = ?", (owner, task_id))


if __name__ == "__main__":
    tid = create_task(
        raw_input="Should I bump my Roth contributions before year-end?",
        category="finance",
        title="Check Roth contribution room before year-end",
        brief="Samuel asked whether to increase Roth contributions given "
              "current cash position. Needs 2026 limits + YTD contributions.",
        owner="richard",
        priority="normal",
    )
    print(f"Created task {tid}")
    print(json.dumps(list_tasks(), indent=2, default=str))
