"""
Central message router.

Group chat: acts only when bot is @mentioned.
Private chat: acts on every message (if chat is in ALLOWED_CHAT_IDS).

Routes:
  stats keywords  -> show stats directly
  mention alone   -> show menu buttons
  anything else   -> ask Claude
"""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config
from handlers.claude_agent import handle_claude
from handlers.stats import handle_stats
from utils.history import save_message

logger = logging.getLogger(__name__)

_STATS_KEYWORDS = {
    "stats", "stat", "statistics", "score", "scores", "result", "results",
    "winrate", "wins", "missions",
    "\u0441\u0442\u0430\u0442", "\u0441\u0442\u0430\u0442\u0430",
    "\u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430",
    "\u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0443",
    "\u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442",
    "\u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u0438",
    "\u0440\u0430\u0445\u0443\u043d\u043e\u043a",
    "\u043f\u0435\u0440\u0435\u043c\u043e\u0433\u0438",
    "\u0432\u0456\u043d\u0440\u0435\u0439\u0442",
}


def _sender_name(update: Update) -> str:
    user = update.message.from_user
    return user.username or user.first_name or f"user_{user.id}"


def _has_stats_intent(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _STATS_KEYWORDS)


async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    text = message.text
    chat_id = update.effective_chat.id
    is_private = update.effective_chat.type == "private"

    if config.ALLOWED_CHAT_IDS and chat_id not in config.ALLOWED_CHAT_IDS:
        logger.debug(f"Ignored message from unlisted chat {chat_id}")
        return

    if config.CLAUDE_MEMORY:
        save_message(
            chat_id=chat_id,
            user_id=update.message.from_user.id,
            username=_sender_name(update),
            text=text,
        )

    if not is_private:
        bot_tag = f"@{config.BOT_USERNAME}"
        if bot_tag.lower() not in text.lower():
            return

    bot_tag = f"@{config.BOT_USERNAME}"
    clean = text.lower().replace(bot_tag.lower(), "").strip()

    if _has_stats_intent(clean):
        logger.info(f"Stats requested by {_sender_name(update)} in chat {chat_id}")
        await handle_stats(update, context)

    elif not clean:
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Log result", callback_data="menu_log"),
                InlineKeyboardButton("Stats", callback_data="menu_stats"),
            ]
        ])
        await message.reply_text("What would you like to do?", reply_markup=keyboard)

    else:
        logger.info(f"Claude invoked by {_sender_name(update)} in chat {chat_id}")
        await handle_claude(update, context)
