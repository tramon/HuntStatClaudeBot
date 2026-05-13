"""
/doc command handler -- sends a link to the Google Sheet.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

import config

logger = logging.getLogger(__name__)


async def cmd_doc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/doc -- send a link to the Google Sheet (allowed chats only)."""
    chat_id = update.effective_chat.id

    if config.ALLOWED_CHAT_IDS and chat_id not in config.ALLOWED_CHAT_IDS:
        return

    if not config.GOOGLE_SHEET_ID:
        await update.message.reply_text("Google Sheet ID is not configured.")
        return

    url = f"https://docs.google.com/spreadsheets/d/{config.GOOGLE_SHEET_ID}"
    await update.message.reply_text(
        f'<a href="{url}">Hunt Stats — Google Sheet</a>',
        parse_mode="HTML",
    )
