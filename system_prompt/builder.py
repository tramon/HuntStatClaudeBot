"""
System prompt builder.

Single place where the full Claude system prompt is assembled at runtime.
Combines static parts (persona + rules) with dynamic context (knowledge base, chat history).

Usage:
    from system_prompt.builder import build_system_prompt
    system = build_system_prompt(query="...", chat_id=123)
"""

import logging

import config

logger = logging.getLogger(__name__)


def build_system_prompt(query: str = "", chat_id: int | None = None) -> str:
    """
    Assemble the full system prompt for a given query and chat.

    1. Base: PERSONA + RULES (always present)
    2. Knowledge base block (if query matches any topic keywords)
    3. Chat history block (if CLAUDE_MEMORY=true and chat_id is given)
    """
    from system_prompt import SYSTEM_PROMPT

    system = SYSTEM_PROMPT

    # --- Knowledge base ---
    if query:
        from utils.knowledge import get_relevant_knowledge
        knowledge = get_relevant_knowledge(query)
        if knowledge:
            system += (
                "\n\n---\n"
                "KNOWLEDGE BASE -- SINGLE SOURCE OF TRUTH:\n"
                + knowledge
                + "\n\n---\n"
                "STRICT RULES when knowledge base is present:\n"
                "- Answer ONLY from the knowledge base above. Do not add, invent, or extrapolate.\n"
                "- If the answer is not in the knowledge base, say so clearly. Do not guess.\n"
                "- Numbers, names, costs, and mechanics must match the knowledge base exactly.\n"
                "- Stay in character, but accuracy beats personality."
            )

    # --- Chat history ---
    if config.CLAUDE_MEMORY and chat_id is not None:
        from utils.history import get_recent_messages
        recent = get_recent_messages(chat_id)
        if recent:
            lines = [f"{m.get('username', 'user')}: {m['text']}" for m in recent]
            system += (
                "\n\nRecent chat history (already answered -- do NOT repeat these):\n"
                + "\n".join(lines)
            )

    return system


def build_announcement_prompt(history_text: str = "") -> str:
    """
    Assemble system prompt for scheduled announcements.

    Always injects the full knowledge base so Claude never invents
    trait names, weapon stats, or mob mechanics.
    Also injects chat history so Claude avoids repeating recent topics.
    """
    from system_prompt import SYSTEM_PROMPT
    from utils.knowledge import get_all_knowledge

    system = SYSTEM_PROMPT

    # Full KB -- prevents hallucinated trait/weapon/mob names
    knowledge = get_all_knowledge()
    if knowledge:
        system += (
            "\n\n---\n"
            "KNOWLEDGE BASE -- SINGLE SOURCE OF TRUTH:\n"
            + knowledge
            + "\n\n---\n"
            "STRICT RULES:\n"
            "- For any game fact (trait, weapon, mob, mechanic) use ONLY the knowledge base above.\n"
            "- If a topic is not covered -- speak generally or pick a different topic.\n"
            "- Never invent names, stats, or mechanics."
        )

    if history_text:
        system += (
            "\n\n---\n"
            "ОСТАННІ ПОВІДОМЛЕННЯ ЧАТУ"
            " (контекст -- не повторюй теми які вже нещодавно обговорювались):\n"
            + history_text
            + "\n---"
        )

    return system
