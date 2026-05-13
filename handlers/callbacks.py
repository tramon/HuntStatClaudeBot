"""
Inline keyboard callback handlers.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from handlers.stats import handle_stats


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the Log result and Stats buttons from the mention menu."""
    query = update.callback_query
    await query.answer()

    if query.data == "menu_log":
        await query.edit_message_text(
            "<b>Log a session result</b>\n\n"
            "Send the command with your result:\n"
            "<code>/log won/total</code>\n\n"
            "Example:  <code>/log 6/12</code>",
            parse_mode="HTML",
        )
    elif query.data == "menu_stats":
        await query.delete_message()
        await handle_stats(update, context)
