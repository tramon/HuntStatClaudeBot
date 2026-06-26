"""
/broadcast command -- owner-only, private chat only.

Usage (in private chat with the bot):
  /broadcast Привіт, мисливці!
  /bc Текст повідомлення

The bot forwards the message text to all chats in ALLOWED_CHAT_IDS.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

import config

logger = logging.getLogger(__name__)


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    user = update.effective_user

    # Owner only
    if not config.OWNER_USER_ID or user.id != config.OWNER_USER_ID:
        await message.reply_text("Not authorized.")
        return

    # Private chat only
    if update.effective_chat.type != "private":
        await message.reply_text("Use this command in private chat with the bot.")
        return

    # Extract text after the command
    text = (message.text or "").strip()
    for cmd in ("/broadcast", "/bc", "/send"):
        if text.lower().startswith(cmd):
            text = text[len(cmd):].strip()
            break

    if not text:
        await message.reply_text(
            "Usage: /broadcast <text>\n"
            "Example: /broadcast Увага, мисливці!"
        )
        return

    if not config.ALLOWED_CHAT_IDS:
        await message.reply_text("ALLOWED_CHAT_IDS is empty -- nowhere to send.")
        return

    sent, failed = 0, 0
    for chat_id in config.ALLOWED_CHAT_IDS:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text)
            sent += 1
            logger.info(f"Broadcast sent to {chat_id} by owner {user.id}")
        except Exception as e:
            failed += 1
            logger.error(f"Broadcast failed for {chat_id}: {e}")

    summary = f"Sent to {sent} chat(s)."
    if failed:
        summary += f" Failed: {failed}."
    await message.reply_text(summary)
