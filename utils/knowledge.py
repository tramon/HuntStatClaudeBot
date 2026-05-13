"""
Knowledge base loader.

Maps topic keywords to local Markdown files in the knowledge/ directory.
Returns relevant file content to inject into the system prompt.
"""

import logging
import os

logger = logging.getLogger(__name__)

_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "knowledge")

# keyword (lowercase) -> knowledge file name
_TOPIC_MAP: dict[str, str] = {
    # traits / perks
    "trait":        "hunt_showdown_1896_traits.md",
    "traits":       "hunt_showdown_1896_traits.md",
    "perk":         "hunt_showdown_1896_traits.md",
    "perks":        "hunt_showdown_1896_traits.md",
    "трейт":        "hunt_showdown_1896_traits.md",
    "трейти":       "hunt_showdown_1896_traits.md",
    "перк":         "hunt_showdown_1896_traits.md",
    "перки":        "hunt_showdown_1896_traits.md",
    "upgrade point": "hunt_showdown_1896_traits.md",
    "билд":         "hunt_showdown_1896_traits.md",
    "build":        "hunt_showdown_1896_traits.md",
    "tier list":    "hunt_showdown_1896_traits.md",
    "тир":          "hunt_showdown_1896_traits.md",
    "синергі":      "hunt_showdown_1896_traits.md",
    "synergy":      "hunt_showdown_1896_traits.md",
}


def _load_file(filename: str) -> str:
    path = os.path.join(_BASE, filename)
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning(f"Knowledge file not found: {path}")
        return ""
    except Exception as e:
        logger.error(f"Failed to load knowledge file {filename}: {e}")
        return ""


def get_relevant_knowledge(text: str) -> str:
    """Return knowledge file content relevant to the query, or empty string.

    Matches keywords case-insensitively. Returns content of the first matched file.
    When multiple files match the same query, they are deduplicated.
    """
    lower = text.lower()
    matched_files: list[str] = []

    for keyword, filename in _TOPIC_MAP.items():
        if keyword in lower and filename not in matched_files:
            matched_files.append(filename)

    if not matched_files:
        return ""

    parts = []
    for filename in matched_files:
        content = _load_file(filename)
        if content:
            parts.append(content)
            logger.info(f"Knowledge loaded: {filename}")

    return "\n\n---\n\n".join(parts)
