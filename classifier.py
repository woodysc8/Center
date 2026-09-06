"""
classifier.py — turns a raw message into the fields create_task() needs
(category, title, brief, owner, priority).

Ships with a rule-based classifier so this works out of the box with zero
API keys or dependencies — good enough to test the full pipeline today.
A real LLM classifier (Gemini, to match Sheila's stack) is stubbed below;
swap CLASSIFY_FN at the bottom once GEMINI_API_KEY is set and you've decided
it's worth the extra cost/latency for better classification.

This is the piece Copilot should feel free to replace outright — the
contract is just: classify(raw_input: str) -> dict with the five fields
below. Everything else in Center only depends on that contract, not on how
it's implemented.
"""

import re
from config import GEMINI_API_KEY

# --- Rule-based fallback -----------------------------------------------

_KEYWORDS = {
    "finance": ["roth", "401k", "budget", "spend", "invest", "credit card",
                "rent", "bilt", "tax", "retirement", "savings", "bank"],
    "travel": ["flight", "hotel", "trip", "travel", "expedia", "skyscanner",
               "book a", "itinerary", "vacation"],
    "research": ["research", "look into", "find out", "what's the latest",
                 "compare", "news on"],
    "reminder": ["remind me", "don't forget", "call ", "text ", "email "],
}

_OWNER_FOR_CATEGORY = {
    "finance": "richard",
    "travel": "juan_whey",
    "research": "unassigned",  # goes to the researcher once it exists
    "reminder": "sheila",
    "unsure": "unassigned",
}


def _rule_based_classify(raw_input: str) -> dict:
    text = raw_input.lower()
    category = "unsure"
    for cat, keywords in _KEYWORDS.items():
        if any(kw in text for kw in keywords):
            category = cat
            break

    # crude priority bump — real ones matter more than rule-based guessing,
    # but "asap"/"urgent" is a cheap, reliable signal
    priority = "high" if re.search(r"\basap\b|\burgent\b", text) else "normal"

    title = raw_input.strip().rstrip(".")[:80]
    brief = (
        f"Samuel said: \"{raw_input.strip()}\" — classified as '{category}' "
        f"by rule-based fallback (no LLM classification available)."
    )

    return {
        "category": category,
        "title": title,
        "brief": brief,
        "owner": _OWNER_FOR_CATEGORY[category],
        "priority": priority,
    }


# --- LLM upgrade path (not active by default) ---------------------------

def _llm_classify(raw_input: str) -> dict:
    """
    Placeholder for a real Gemini call. Left unimplemented on purpose —
    wire this up once GEMINI_API_KEY is set and you want better-than-keyword
    classification. The prompt below is a starting point for whoever (you or
    Copilot) implements it.
    """
    system_prompt = """You are a task classifier for a personal AI network.
Given a message, output ONLY a JSON object with these fields:
- category: one of "finance", "travel", "research", "reminder", "unsure"
- title: a short (<80 char) summary
- brief: 2-4 sentences a specialist AI would need to act on this, written
  in third person about Samuel
- owner: one of "richard" (finance), "juan_whey" (travel), "sheila"
  (reminders/small stuff), "samuel" (needs his direct input), "unassigned"
  (research or unclear)
- priority: one of "low", "normal", "high"
No preamble, no markdown fences, just the JSON object."""
    raise NotImplementedError(
        "Wire this up to the Gemini API using GEMINI_API_KEY once you want "
        "LLM-based classification. See system_prompt above as a starting point."
    )


def classify(raw_input: str) -> dict:
    """The one function everything else calls. Swap the body to switch
    between rule-based and LLM classification."""
    if GEMINI_API_KEY:
        try:
            return _llm_classify(raw_input)
        except NotImplementedError:
            pass  # fall through to rule-based until _llm_classify is built
    return _rule_based_classify(raw_input)


if __name__ == "__main__":
    import json
    for example in [
        "Should I bump my Roth contributions before year-end?",
        "Remind me to call Nora tomorrow",
        "Find me flights to Lisbon in October",
        "What's the latest on fintech PR trends?",
        "urgent - my card got declined",
    ]:
        print(example, "->", json.dumps(classify(example)))
