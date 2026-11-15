"""
System prompt builder.

Single place where the Claude system prompt is assembled at runtime.
Returns a list of system blocks:
  1. persona + rules                (static)
  2. knowledge base                 (only when the query matches; cached by the API)
  3. current date + game-version    (changes, so it stays last and uncached)

Recent chat history is NOT part of the system prompt: build_history_block()
returns it as a transcript that goes into the user message.
"""

import logging
from datetime import datetime, timezone

import config

logger = logging.getLogger(__name__)

# Newest game update that the knowledge base was checked against.
_LATEST_KNOWN_UPDATE = "2.9.1 (October 2026)"

_KB_HEADER = (
    "KNOWLEDGE BASE -- ADDITIONAL REFERENCE:\n"
)
_KB_FOOTER = (
    "\n\n---\n"
    "Use the knowledge base above as a helpful reference together with everything you already know.\n"
    "You are not limited to it -- feel free to add your own knowledge and context."
)


def _now_line() -> str:
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Europe/Kyiv"))
        tz = "Kyiv"
    except Exception:
        now = datetime.now(timezone.utc)
        tz = "UTC"
    return f"{now:%Y-%m-%d %H:%M} ({now:%A}, {tz} time)"


def _tail_text() -> str:
    return (
        f"Current date and time: {_now_line()}.\n"
        f"The newest game update covered by your knowledge base is {_LATEST_KNOWN_UPDATE}; "
        "newer patches or events may exist. If someone asks about the current patch, event, "
        "prices or meta, check with web_search."
    )


def build_system_prompt(query: str = "", chat_id: int | None = None) -> list[dict]:
    """
    Assemble the system prompt blocks for a given query.

    chat_id is accepted for backward compatibility; chat history is added
    to the user message via build_history_block().
    """
    from system_prompt import SYSTEM_PROMPT

    blocks: list[dict] = [{"type": "text", "text": SYSTEM_PROMPT}]

    if query:
        from utils.knowledge import get_relevant_knowledge
        knowledge = get_relevant_knowledge(query)
        if knowledge:
            blocks.append({
                "type": "text",
                "text": _KB_HEADER + knowledge + _KB_FOOTER,
                # Cache everything up to here: the same KB is often asked about several times in a row.
                "cache_control": {"type": "ephemeral"},
            })

    blocks.append({"type": "text", "text": _tail_text()})
    return blocks


def build_history_block(chat_id: int | None, current_text: str = "") -> str:
    """Recent chat messages as a transcript for the user message ('' if memory is off or empty)."""
    if not (config.CLAUDE_MEMORY and chat_id is not None):
        return ""

    from utils.history import get_recent_messages
    recent = get_recent_messages(chat_id)
    # The current message is saved before routing -- drop it so it is not shown twice.
    if recent and current_text and recent[-1].get("text") == current_text:
        recent = recent[:-1]

    lines = []
    for m in recent:
        text = str(m.get("text", "")).replace("\n", " ").strip()
        if len(text) > 300:
            text = text[:300] + "…"
        if text:
            lines.append(f"{m.get('username', 'user')}: {text}")
    if not lines:
        return ""
    return (
        "Recent chat messages (context only -- answer the last message below):\n"
        + "\n".join(lines)
        + "\n\n---\n"
    )


def build_announcement_prompt(history_text: str = "") -> list[dict]:
    """
    Assemble system prompt blocks for scheduled announcements.

    Always injects the full knowledge base as an additional reference.
    Also injects chat history so Claude avoids repeating recent topics.
    """
    from system_prompt import SYSTEM_PROMPT
    from utils.knowledge import get_all_knowledge

    blocks: list[dict] = [{"type": "text", "text": SYSTEM_PROMPT}]

    knowledge = get_all_knowledge()
    if knowledge:
        blocks.append({"type": "text", "text": _KB_HEADER + knowledge + _KB_FOOTER})

    if history_text:
        blocks.append({
            "type": "text",
            "text": (
                "ОСТАННІ ПОВІДОМЛЕННЯ ЧАТУ"
                " (контекст -- не повторюй теми які вже нещодавно обговорювались):\n"
                + history_text
            ),
        })

    blocks.append({"type": "text", "text": _tail_text()})
    return blocks
