"""Fixed registry for Center's structured capabilities."""

from collections.abc import Callable
from typing import Any

from . import calendar_read, gmail_read


Capability = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]

_CAPABILITIES: dict[str, Capability] = {
    "calendar_read": calendar_read.execute,
    "gmail_read": gmail_read.execute,
}


def get_capability(name: str) -> Capability | None:
    """Resolve a registered capability without dynamic discovery."""
    return _CAPABILITIES.get(name)
