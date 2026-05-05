"""
Slash command handlers — work independently of Claude.

/log 6/12   — record a session result win / games
/log 6/12/1   — record a session result win / games / server wipes
/log        — show usage instructions
/stats      — show aggregate stats
"""

import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from handlers.stats import handle_stats
from utils.sheets import append_session

logger = logging.getLogger(__name__)

# Matches: 6/12  or  6/12/1  (third number is optional — server wipes)
_RESULT_RE = re.compile(r"(\d+)\s*/\s*(\d+)(?:\s*/\s*(\d+))?")  # 6/12 or 6/12/1


def _sender_name(update: Update) -> str:
    msg = update.message or update.effective_message
    if not msg:
        return "unknown"
    user = msg.from_user
    return user.username or user.first_name or f"user_{user.id}"


async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /log 6/12    — saves won/total to Google Sheets
    /log 6/12/1  — saves won/total/wipes to Google Sheets
    /log         — shows usage hint with inline button
    """
    args = " ".join(context.args) if context.args else ""
    match = _RESULT_RE.search(args)

    if not match:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 How to log a result", callback_data="log_help")]
        ])
        await update.message.reply_text(
            "📝 <b>Log a session result</b>\n\n"
            "Send the command with your result:\n"
            "<code>/log won/total</code>\n\n"
            "Example:  <code>/log 6/12</code>",
            parse_mode="HTML",
            reply_markup=keyboard,
        )
        return

    won = int(match.group(1))
    total = int(match.group(2))
    wipes = int(match.group(3)) if match.group(3) is not None else 0

    if total == 0:
        await update.message.reply_text("⚠️ Total can't be zero.")
        return

    if won > total:
        await update.message.reply_text(
            f"⚠️ Won ({won}) can't be greater than total ({total})."
        )
        return

    win_rate = round(won / total * 100)

    append_session(won=won, total=total, wipes=wipes)
    logger.info(f"Session logged: {won}/{total}, wipes={wipes} by {_sender_name(update)}")

    wipes_line = f"\nServer wipes: <b>{wipes}</b>" if wipes > 0 else ""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 View stats", callback_data="menu_stats")]
    ])

    await update.message.reply_text(
        f"✅ <b>Session saved!</b>\n"
        f"Won <b>{won}</b> out of <b>{total}</b> ({win_rate}%)"
        f"{wipes_line}",
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def cmd_log_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the 'How to log a result' inline button."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📖 <b>How to log a result</b>\n\n"
        "<code>/log won/total</code>\n"
        "<code>/log won/total/wipes</code>\n\n"
        "<code>/log 6/12</code>    — 6 wins out of 12 missions\n"
        "<code>/log 6/12/1</code>  — same + 1 server wipe\n\n"
        "Result is saved to Google Sheets and counted in <code>/stats</code>.",
        parse_mode="HTML",
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stats — show aggregate stats from Google Sheets."""
    await handle_stats(update, context)


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the 📝 Log result and 📊 Stats buttons from the mention menu."""
    query = update.callback_query
    await query.answer()

    if query.data == "menu_log":
        await query.edit_message_text(
            "📝 <b>Log a session result</b>\n\n"
            "Send the command with your result:\n"
            "<code>/log won/total</code>\n\n"
            "Example:  <code>/log 6/12</code>",
            parse_mode="HTML",
        )
    elif query.data == "menu_stats":
        await query.delete_message()
        await handle_stats(update, context)
