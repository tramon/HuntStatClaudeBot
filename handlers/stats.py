"""
Stats handler — reads from Google Sheets and returns aggregate summary.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from utils.sheets import get_all_sessions

logger = logging.getLogger(__name__)


async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sessions = get_all_sessions()

    if not sessions:
        await context.bot.send_message(
            update.effective_chat.id,
            "📊 No stats recorded yet.\n\n"
            "Use <code>/log 6/12</code> to log your first session.",
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

    reply = (
        f"📊 <b>Hunt Stats</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Sessions:   {session_count}\n"
        f"Missions:   {total_missions}\n"
        f"Wins:       {total_won}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"<b>Win rate:  {overall_pct}%</b>\n"
        f"Server wipes:  <b>{total_wipes} ({wipes_pct}%)</b>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"Last session ({last['date']}):  "
        f"{last['won']}/{last['total']} = {last['win_pct']}%"
    )

    await context.bot.send_message(
        update.effective_chat.id,
        reply,
        parse_mode="HTML",
    )
