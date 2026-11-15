"""
Central message router.

Group chat: acts when the bot is @mentioned OR when someone replies to one of its messages.
Private chat: acts on every message (if chat is in ALLOWED_CHAT_IDS).

Routes:
  short stats request -> show stats directly
  mention alone       -> show menu buttons
  anything else       -> ask Claude (which can call the stats tool for detailed questions)
"""

import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config
from handlers.claude_agent import create_message, handle_claude
from handlers.stats import handle_stats
from utils.history import save_message
from utils.telegram_text import safe_reply

logger = logging.getLogger(__name__)

# Whole words that mean "show the stats".
_STATS_WORDS = {
    "stats", "stat", "score", "scores", "winrate", "wins", "missions",
    "стат", "стата", "стату", "статс", "рахунок", "вінрейт",
}
# Word beginnings (statistics / статистика, результат(и), ...).
_STATS_PREFIXES = ("statistic", "result", "статистик", "результат", "перемог")

# Only short messages take the fast stats path; longer, nuanced questions go to Claude,
# which has the get_hunt_stats tool.
_STATS_MAX_WORDS = 6


def _sender_name(update: Update) -> str:
    user = update.message.from_user
    return user.username or user.first_name or f"user_{user.id}"


def _has_stats_intent(text: str) -> bool:
    words = re.findall(r"[\w'’]+", text.lower())
    if not words or len(words) > _STATS_MAX_WORDS:
        return False
    return any(w in _STATS_WORDS or w.startswith(_STATS_PREFIXES) for w in words)


def _is_reply_to_bot(message, context: ContextTypes.DEFAULT_TYPE) -> bool:
    quoted = message.reply_to_message
    return bool(quoted and quoted.from_user and quoted.from_user.id == context.bot.id)


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

    bot_tag = f"@{config.BOT_USERNAME}".lower()
    mentioned = bot_tag in text.lower()

    if not is_private and not mentioned and not _is_reply_to_bot(message, context):
        return

    clean = text.lower().replace(bot_tag, "").strip()

    if _has_stats_intent(clean):
        logger.info(f"Stats requested by {_sender_name(update)} in chat {chat_id}")
        await handle_stats(update, context)

    elif not clean:
        # Bare @mention -- Claude responds and keyboard is attached to the reply
        logger.info(f"Bare mention by {_sender_name(update)} in chat {chat_id}")
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Log result", callback_data="menu_log"),
                InlineKeyboardButton("Stats", callback_data="menu_stats"),
            ]
        ])
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        from system_prompt.builder import build_system_prompt
        sender = _sender_name(update)
        try:
            resp = await create_message(
                model=config.CLAUDE_MODEL,
                max_tokens=600,
                system=build_system_prompt(chat_id=chat_id),
                messages=[{"role": "user", "content": f"{sender} just @mentioned you with no message."}],
                output_config={"effort": config.CLAUDE_EFFORT},
            )
            reply = resp.content[0].text.strip() or "?"
        except Exception:
            reply = "?"
        await safe_reply(message, reply, reply_markup=keyboard)

    else:
        logger.info(f"Claude invoked by {_sender_name(update)} in chat {chat_id}")
        await handle_claude(update, context)
