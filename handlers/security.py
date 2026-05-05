"""
Security handler — keeps the bot out of unauthorized groups.

When the bot is added to any chat, this handler fires first.
If ALLOWED_CHAT_IDS is set and the chat is not on the list,
the bot logs the chat ID (so you can whitelist it if needed) and leaves.

If ALLOWED_CHAT_IDS is empty, the bot accepts all chats — useful during
the very first run when you don't know your group's chat ID yet.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

import config

logger = logging.getLogger(__name__)


async def handle_new_chat_member(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    # Only act when the bot itself was added (not other users)
    new_status = update.my_chat_member.new_chat_member.status
    if new_status not in ("member", "administrator"):
        return

    chat = update.effective_chat
    chat_id = chat.id
    chat_title = chat.title or "unknown"

    logger.info(f"Bot added to chat — id={chat_id}, title='{chat_title}'")

    # No whitelist configured → allow (useful during initial setup)
    if not config.ALLOWED_CHAT_IDS:
        logger.warning(
            f"ALLOWED_CHAT_IDS is not set. "
            f"Add this to your .env to restrict access:  ALLOWED_CHAT_IDS={chat_id}"
        )
        return

    if chat_id not in config.ALLOWED_CHAT_IDS:
        logger.warning(
            f"Unauthorized chat {chat_id} ('{chat_title}') — leaving. "
            f"Add {chat_id} to ALLOWED_CHAT_IDS if this was intentional."
        )
        await context.bot.leave_chat(chat_id)
