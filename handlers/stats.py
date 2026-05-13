"""
Stats handler -- reads from Google Sheets and returns aggregate summary.

handle_stats  -- shared logic (called by mention router and callbacks)
cmd_stats     -- /stats command entry point
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from utils.sheets import SheetsError, get_all_sessions

logger = logging.getLogger(__name__)


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        sessions = get_all_sessions()
    except SheetsError as e:
        logger.error(f"Stats fetch failed: {e}")
        await context.bot.send_message(
            update.effective_chat.id,
            f"Could not load stats: {e}",
            parse_mode="HTML",
        )
        return

    if not sessions:
        await context.bot.send_message(
            update.effective_chat.id,
            "No stats recorded yet.\n\nUse <code>/log 6/12</code> to log your first session.",
            parse_mode="HTML",
        )
        return

    total_won = sum(s["won"] for s in sessions)
    total_missions = sum(s["total"] for s in sessions)
    total_wipes = sum(s["wipes"] for s in sessions)
    session_count = len(sessions)

    overall_pct = round(total_won / total_missions * 100) if total_missions > 0 else 0
    wipes_pct = round(total_wipes / total_missions * 100, 2) if total_missions > 0 else 0

    last = sessions[-1]

    lines = [
        "<b>Hunt Stats</b>",
        "---------------",
        f"Sessions:     {session_count}",
        f"Missions:     {total_missions}",
        f"Wins:         {total_won}",
        "---------------",
        f"<b>Win rate:  {overall_pct}%</b>",
        f"Server wipes: <b>{total_wipes} ({wipes_pct}%)</b>",
        "---------------",
        f"Last session ({last['date']}):  {last['won']}/{last['total']} = {last['win_pct']}%",
    ]
    reply = "\n".join(lines)

    await context.bot.send_message(
        update.effective_chat.id,
        reply,
        parse_mode="HTML",
    )


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/stats command -- delegates to handle_stats."""
    await handle_stats(update, context)
