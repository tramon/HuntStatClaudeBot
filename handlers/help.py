"""
/help command handler.
"""

from telegram import Update
from telegram.ext import ContextTypes


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/help -- show all available commands."""
    await update.message.reply_text(
        "<b>HuntStatBot commands</b>\n\n"
        "<code>/log win/missions</code>\n"
        "Log a session result.\n"
        "Example: <code>/log 6/12</code>\n\n"
        "<code>/log win/missions/wipes</code>\n"
        "Log with server wipes.\n"
        "Example: <code>/log 6/12/1</code>\n\n"
        "<code>/stats</code>\n"
        "Show overall hunt statistics.\n\n"
        "<code>/doc</code>\n"
        "Link to the Google Sheet.\n\n"
        "<code>@HuntStatClaudeBot question</code>\n"
        "Ask Claude anything.",
        parse_mode="HTML",
    )
