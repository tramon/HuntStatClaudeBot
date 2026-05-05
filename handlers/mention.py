"""
Central message router.

When the bot is @mentioned in the group:
  - "stats" / "stat"  → show stats from Excel
  - mention alone     → show menu buttons
  - anything else     → ask Claude (no history stored)
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config
from handlers.claude_agent import handle_claude
from handlers.stats import handle_stats
from utils.history import save_message

logger = logging.getLogger(__name__)

_STATS_KEYWORDS = {"stats", "stat", "statistics"}


def _sender_name(update: Update) -> str:
    user = update.message.from_user
    return user.username or user.first_name or f"user_{user.id}"


async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    text = message.text
    chat_id = update.effective_chat.id

    # Optionally save message for Claude context
    if config.CLAUDE_MEMORY:
        save_message(
            chat_id=update.effective_chat.id,
            user_id=update.message.from_user.id,
            username=_sender_name(update),
            text=text,
        )

    # Only act when the bot is @mentioned
    bot_tag = f"@{config.BOT_USERNAME}"
    if bot_tag.lower() not in text.lower():
        return

    # Strip leading slashes so "/stat" matches "stat", remove the bot mention itself
    words = {w.lstrip("/") for w in text.lower().split()}
    words.discard(bot_tag.lower())

    if words & _STATS_KEYWORDS:
        logger.info(f"Stats requested by {_sender_name(update)} in chat {chat_id}")
        await handle_stats(update, context)

    elif not words:
        # Mentioned alone — show menu buttons
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📝 Log result", callback_data="menu_log"),
                InlineKeyboardButton("📊 Stats",      callback_data="menu_stats"),
            ]
        ])
        await message.reply_text(
            "What would you like to do?",
            reply_markup=keyboard,
        )

    else:
        logger.info(f"Claude invoked by {_sender_name(update)} in chat {chat_id}")
        await handle_claude(update, context)
