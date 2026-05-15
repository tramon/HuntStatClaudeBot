"""
Announcement scheduler.

Reads ANNOUNCEMENTS from announcements.py and schedules them
using APScheduler with cron triggers (Europe/Kyiv timezone).
All announcements are sent to every chat in ALLOWED_CHAT_IDS.

Each entry supports either:
  "text"   -- static string (or lambda) sent as-is
  "prompt" -- instruction for Claude; text is generated at send time
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

import config

logger = logging.getLogger(__name__)

_TZ = "Europe/Kyiv"


async def _generate_text(prompt: str) -> str | None:
    """Ask Claude to generate announcement text. Returns None on failure."""
    try:
        from handlers.claude_agent import _get_client, SYSTEM_PROMPT
        response = _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=200,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude announcement generation failed: {e}")
        return None


def _make_job(bot: Bot, entry: dict):
    """Return an async job that resolves text (static or Claude) and sends it."""
    async def job():
        # Resolve text
        if "prompt" in entry:
            text = await _generate_text(entry["prompt"])
            if not text:
                logger.warning("Claude unavailable -- announcement skipped")
                return
        else:
            raw = entry["text"]
            text = raw() if callable(raw) else raw

        # Send to all allowed chats
        for chat_id in config.ALLOWED_CHAT_IDS:
            try:
                await bot.send_message(chat_id=chat_id, text=text)
                logger.info(f"Announcement sent to {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send announcement to {chat_id}: {e}")

    return job


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Create, populate and return the scheduler (not yet started)."""
    try:
        from announcements import ANNOUNCEMENTS
    except ImportError:
        logger.warning("announcements.py not found -- scheduler disabled")
        return AsyncIOScheduler()

    if not config.ALLOWED_CHAT_IDS:
        logger.warning("ALLOWED_CHAT_IDS is empty -- announcements will not be sent")

    scheduler = AsyncIOScheduler(timezone=_TZ)

    registered = 0
    for idx, entry in enumerate(ANNOUNCEMENTS):
        cron = entry.get("cron", "")
        has_text   = bool(entry.get("text"))
        has_prompt = bool(entry.get("prompt"))

        if not cron or not (has_text or has_prompt):
            logger.warning(f"Announcement #{idx} is incomplete -- skipped")
            continue

        try:
            parts = cron.split()
            if len(parts) != 5:
                raise ValueError(f"Expected 5 cron fields, got {len(parts)}")
            minute, hour, day, month, day_of_week = parts
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=_TZ,
            )
        except Exception as e:
            logger.error(f"Announcement #{idx} bad cron {cron!r}: {e} -- skipped")
            continue

        mode = "claude" if has_prompt else "static"
        scheduler.add_job(_make_job(bot, entry), trigger)
        registered += 1
        logger.info(f"Announcement #{idx} scheduled: cron={cron!r} mode={mode}")

    logger.info(f"Scheduler ready: {registered} announcement(s) registered")
    return scheduler
