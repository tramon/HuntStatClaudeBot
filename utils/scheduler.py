"""
Announcement scheduler.

Reads ANNOUNCEMENTS from announcements.py and schedules them
using APScheduler with cron triggers (Europe/Kyiv timezone).
All announcements are sent to every chat in ALLOWED_CHAT_IDS.

Prompt building for Claude-generated announcements is handled
by persona.builder.build_announcement_prompt.
"""

import logging
import random
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.base import BaseTrigger
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

import config

logger = logging.getLogger(__name__)

_TZ = "Europe/Kyiv"
_MSG_TRUNCATE = 120  # max chars per history line


class DateJitterTrigger(BaseTrigger):
    """Cron trigger whose random delay is derived from the date, not from memory.

    The bot runs in ~6-hour relays and its state is wiped on every restart. A normal
    random jitter is re-rolled at each start, so a restart could skip today's
    announcement or fire it twice. Here the offset of a given day is always the same
    (seeded by salt + date), so the fire time of "today" is identical before and after
    any restart: if it is still ahead it fires once, if it has passed it is not repeated.
    """

    def __init__(self, cron: CronTrigger, jitter: int, salt: str = ""):
        self.cron = cron
        self.jitter = max(int(jitter), 1)
        self.salt = salt

    def _fire_time(self, base: datetime) -> datetime:
        rng = random.Random(f"{self.salt}-{base:%Y-%m-%d}")
        return base + timedelta(seconds=rng.randrange(self.jitter))

    def get_next_fire_time(self, previous_fire_time, now):
        # A base cron time up to `jitter` seconds ago may still be waiting for its offset.
        base = self.cron.get_next_fire_time(None, now - timedelta(seconds=self.jitter))
        while base is not None:
            fire = self._fire_time(base)
            if fire > now and (previous_fire_time is None or fire > previous_fire_time):
                return fire
            base = self.cron.get_next_fire_time(base, base + timedelta(seconds=1))
        return None

    def __str__(self):
        return f"date-jitter[{self.jitter}s, {self.cron}]"


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
        from handlers.claude_agent import create_message
        from system_prompt.builder import build_announcement_prompt
        system = build_announcement_prompt(history_text)
        response = await create_message(
            model=config.CLAUDE_MODEL,
            max_tokens=800,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": config.CLAUDE_EFFORT},
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

        # Resolve prompt -- may be a callable (e.g. date-seeded topic picker)
        raw_prompt = entry["prompt"]
        prompt = raw_prompt() if callable(raw_prompt) else raw_prompt

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

            text = await _generate_text(prompt, history_text)
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
                day_of_week=dow, timezone=_TZ,
            )
            if jitter:
                trigger = DateJitterTrigger(trigger, jitter, salt=f"announcement-{idx}")
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
