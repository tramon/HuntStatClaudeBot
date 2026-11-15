"""
Helpers for sending Claude's answers to Telegram safely.

format_reply  -- turn the few markdown bits Claude may emit into Telegram HTML
split_message -- cut long text below Telegram's 4096-character limit
safe_reply    -- reply with formatting, split if needed, fall back to plain text
"""

import html
import re

from telegram.error import BadRequest

_LIMIT = 4000  # Telegram hard limit is 4096; leave room for HTML escaping

_HEADER = re.compile(r"^[ \t]{0,3}#{1,6}[ \t]*", re.M)
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
_CODE = re.compile(r"`([^`\n]+)`")


def format_reply(text: str) -> str:
    """Escape HTML, drop markdown headers, convert **bold** and `code`."""
    t = _HEADER.sub("", text.strip())
    t = html.escape(t, quote=False)
    t = _BOLD.sub(r"<b>\1</b>", t)
    t = _CODE.sub(r"<code>\1</code>", t)
    return t


def split_message(text: str, limit: int = _LIMIT) -> list[str]:
    """Split text into chunks <= limit, preferring paragraph/line/word boundaries."""
    rest = (text or "").strip()
    if not rest:
        return []
    chunks: list[str] = []
    while len(rest) > limit:
        cut = rest.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = rest.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = rest.rfind(" ", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    if rest:
        chunks.append(rest)
    return chunks


async def safe_reply(message, text: str, reply_markup=None):
    """Reply to a message; never fails on formatting or length. Returns the last sent message."""
    chunks = split_message(text) or ["…"]
    sent = None
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        try:
            sent = await message.reply_text(format_reply(chunk), parse_mode="HTML", reply_markup=markup)
        except BadRequest:
            sent = await message.reply_text(chunk, reply_markup=markup)
    return sent
