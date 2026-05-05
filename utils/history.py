"""
Optional message history for Claude context.
Only used when CLAUDE_MEMORY=true in .env

Stores a rolling window of recent messages in data/messages.json
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import config

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MESSAGES_FILE = os.path.join(_BASE_DIR, "data", "messages.json")


def _load() -> list[dict[str, Any]]:
    if not os.path.exists(MESSAGES_FILE):
        return []
    try:
        with open(MESSAGES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save(data: list[dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(MESSAGES_FILE), exist_ok=True)
    with open(MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def save_message(chat_id: int, user_id: int, username: str, text: str) -> None:
    messages = _load()
    messages.append({
        "chat_id": chat_id,
        "user_id": user_id,
        "username": username,
        "text": text,
        "date": datetime.now(timezone.utc).isoformat(),
    })
    # Keep a buffer 4x larger than needed
    max_stored = config.CONTEXT_MESSAGES * 4
    if len(messages) > max_stored:
        messages = messages[-max_stored:]
    _save(messages)


def get_recent_messages(chat_id: int) -> list[dict[str, Any]]:
    messages = _load()
    chat_messages = [m for m in messages if m.get("chat_id") == chat_id]
    return chat_messages[-config.CONTEXT_MESSAGES:]
