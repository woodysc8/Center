"""
config.py — shared settings for Center.

Keep this dead simple. Every other module in Center imports from here rather
than hardcoding paths or reading the environment directly, so there's one
place to change when this eventually points at real infrastructure (a hosted
DB, a real API key, etc.) instead of local files.
"""

import os
from pathlib import Path

# Where the tasks table lives. Local file by default — swap for a hosted
# Postgres/Supabase URL later without touching intake.py/ceo.py's logic.
DB_PATH = Path(os.environ.get("CENTER_DB_PATH", "data/center.db"))

# Optional: set this if/when classifier.py should use a real LLM instead of
# its rule-based fallback. Gemini to match Sheila's existing stack, but
# classifier.py doesn't hard-require this — it works without it.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
