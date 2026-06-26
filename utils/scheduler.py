"""
Announcement scheduler.

Reads ANNOUNCEMENTS from announcements.py and schedules them
using APScheduler with cron triggers (Europe/Kyiv timezone).
All announcements are sent to every chat in ALLOWED_CHAT_IDS.

Prompt building for Claude-generated announcements is handled
by persona.builder.build_announcement_prompt.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

import config

logger = logging.getLogger(__name__)

_TZ = "Europe/Kyiv"
_MSG_TRUNCATE = 120  # max chars per history line


def _format_history(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        name = m.get("username", "user")
        text = m.get("text", "").replace("\n", " ").strip()
        if len(text) > _MSG_TRUNCATE:
            text = text[:_MSG_TRUNCATE] + "\u2026"
        if text:
            lines.append(f"{name}: {text}")
    return "\n".join(lines)


async def _generate_text(prompt: str, history_text: str = "") -> str | None:
    try:
        from handlers.claude_agent import _get_client
        from system_prompt.builder import build_announcement_prompt
        system = build_announcement_prompt(history_text)
        response = _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=200,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.error(f"Claude announcement generation failed: {e}")
        return None


def _make_job(bot: Bot, entry: dict):
    async def job():
        has_prompt = bool(entry.get("prompt"))

        if not has_prompt:
            raw = entry["text"]
            text = raw() if callable(raw) else raw
            for chat_id in config.ALLOWED_CHAT_IDS:
                try:
                    await bot.send_message(chat_id=chat_id, text=text)
                    logger.info(f"Announcement sent to {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to send to {chat_id}: {e}")
            return

        for chat_id in config.ALLOWED_CHAT_IDS:
            history_text = ""
            try:
                from utils.history import get_recent_messages
                msgs = get_recent_messages(chat_id, limit=config.CONTEXT_MESSAGES)
                if msgs:
                    history_text = _format_history(msgs)
                    logger.info(f"Loaded {len(msgs)} history msgs for chat {chat_id}")
            except Exception as e:
                logger.warning(f"Could not load history for {chat_id}: {e}")

            text = await _generate_text(entry["prompt"], history_text)
            if not text:
                logger.warning(f"Announcement skipped for chat {chat_id}")
                continue

            try:
                await bot.send_message(chat_id=chat_id, text=text)
                logger.info(f"Announcement sent to {chat_id}")
            except Exception as e:
                logger.error(f"Failed to send to {chat_id}: {e}")

    return job


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
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
            logger.warning(f"Announcement #{idx} incomplete -- skipped")
            continue

        jitter = entry.get("jitter")
        try:
            minute, hour, day, month, dow = cron.split()
            trigger = CronTrigger(
                minute=minute, hour=hour, day=day, month=month,
                day_of_week=dow, timezone=_TZ, jitter=jitter,
            )
        except Exception as e:
            logger.error(f"Announcement #{idx} bad cron {cron!r}: {e} -- skipped")
            continue

        mode = "claude+history" if has_prompt else "static"
        jitter_info = f" jitter={jitter}s" if jitter else ""
        scheduler.add_job(_make_job(bot, entry), trigger)
        registered += 1
        logger.info(f"Announcement #{idx}: cron={cron!r} mode={mode}{jitter_info}")

    logger.info(f"Scheduler ready: {registered} announcement(s) registered")
    return scheduler
