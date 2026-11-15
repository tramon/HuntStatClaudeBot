"""
Scheduled announcements config.

To add a new announcement -- add an entry to ANNOUNCEMENTS.
Messages are sent to ALL chats listed in ALLOWED_CHAT_IDS (from secrets/.env).

Cron format: "minute hour day_of_month month day_of_week"
  0 9 * * 1-5     -> 09:00 Mon-Fri
  0 17 * * 5      -> 17:00 every Friday
  */30 * * * *    -> every 30 minutes

APScheduler day_of_week: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun

Timezone: Europe/Kyiv

Fields:
  "cron"   -- schedule (required)
  "text"   -- static message: str or lambda () -> str
  "prompt" -- Claude generates the message: str or lambda () -> str
  "jitter" -- spread in seconds added to the cron time (optional); the offset is derived from the
             date, so it is the same after a restart (see utils/scheduler.py)
"""

import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

_TZ = ZoneInfo("Europe/Kyiv")

# =============================================================================
# DAILY TOPIC PICKER -- stateless, derived from the date
#
# The bot runs in 6-hour relays on GitHub Actions and its memory is wiped on every
# restart, so nothing here is stored. Today's topic and style are computed from
# the Kyiv date alone: the same day always gives the same pick (a restart cannot
# change it or repeat it), and consecutive days never repeat a topic until the whole
# list has been used.
# =============================================================================

# Conversation starters, NOT advice: the bot asks and jokes, it does not teach.
_TOPICS = [
    "Найдурніша або найсмішніша смерть, яку хтось із групи пам'ятає",
    "Улюблена і найменш улюблена зброя в групі -- запитай, що зараз в кого",
    "Який бос байо дістає найбільше і чому саме він",
    "Звуки гри, від яких усім стає не по собі -- ворони, собаки, кроки, дзвін",
    "Момент, коли все пішло не за планом, але закінчилось добре",
    "Темрява, ліхтарі та страх перед темним кутом компаунду",
    "Вогонь і отрута -- хто в команді найбільше любить палити все навколо",
    "Екстракція в останню секунду -- чи були історії, коли ледве встигли",
    "Хто в групі найчастіше береже тіло тімейта, а хто тікає першим",
    "Легенди і лор Hunt: Showdown -- що в грі найбільше чіпляє атмосферою",
    "Команда мрії: яку трійку мисливців (хантерів) ви б зібрали і чому",
    "Традиції групи перед матчем -- ритуали, прикмети, улюблені локації для старту",
    "Страшні або кумедні випадкові зустрічі з іншими командами",
    "Карта, яку кожен у групі любить або ненавидить найбільше",
    "Дилема: взяти ризик заради боса чи піти на безпечну екстракцію",
]

# How the message is shaped -- again no teaching. Picked by datetime, not remembered.
_STYLES = [
    "Постав групі одне питання і нічого більше.",
    "Скажи сухий жарт або іронічне спостереження про цю тему, без висновків і порад.",
    "Згадай вигадану сценку з байо на цю тему і закінчи питанням до групи.",
    "Запропонуй групі вибір між двома варіантами і спитай, що б вони обрали.",
    "Кинь легку провокацію (жарт, не критику), щоб хтось захотів відповісти.",
]


def _kyiv_now() -> datetime:
    return datetime.now(_TZ)


def _topic_order(cycle: int) -> list[int]:
    """Topic indexes in the order used during one cycle. The same cycle number always
    gives the same order, so it survives restarts without any storage."""
    order = list(range(len(_TOPICS)))
    random.Random(f"topics-{cycle}").shuffle(order)
    return order


def pick_topic(now: datetime | None = None) -> tuple[str, str]:
    """Return (topic, style) for the given moment (defaults to now, Kyiv time).

    - Topic: derived from the day number. A full cycle visits every topic once, then
      a new cycle reshuffles; the first topic of a new cycle is never the previous one.
    - Style: derived from the date-time (day + hour), so it also changes without state.
    """
    now = now or _kyiv_now()
    day = now.date().toordinal()
    n = len(_TOPICS)
    cycle, pos = divmod(day, n)

    order = _topic_order(cycle)
    if pos == 0:
        prev_last = _topic_order(cycle - 1)[-1]
        if order[0] == prev_last:
            order[0], order[1] = order[1], order[0]
    topic = _TOPICS[order[pos]]

    style = _STYLES[random.Random(f"style-{day}-{now.hour}").randrange(len(_STYLES))]
    return topic, style


def _daily_prompt() -> str:
    """Build the daily announcement prompt from the date-derived topic and style."""
    topic, style = pick_topic()
    return (
        "Напиши одне повідомлення в телеграм-групу друзів, що грають у Hunt: Showdown 1896.\n\n"
        f"ТЕМА: {topic}\n"
        f"ФОРМАТ: {style}\n\n"
        "ПРАВИЛО 1 -- Не розкривай тему і не коментуй її вибір. Пиши одразу повідомлення.\n\n"
        "ПРАВИЛО 2 -- НІЯКИХ порад, підказок, рекомендацій і повчань. Не вчи, не пояснюй механіки, "
        "не показуй, що знаєш більше за інших. Ти один із групи, а не наставник.\n\n"
        "ПРАВИЛО 3 -- Якщо в чаті (контекст вище) нещодавно обговорювали цю тему або щось близьке -- "
        "підхопи розмову замість шаблонного повідомлення.\n\n"
        "ПРАВИЛО 4 -- Українською. Без Lebel."
    )


# =============================================================================
# ANNOUNCEMENTS
# =============================================================================

ANNOUNCEMENTS: list[dict] = [
    {
        # One-time joke -- fires once on 2026-06-26, remove after
        "text": (
            "Офіційне повідомлення від The Priest.\n\n"
            "Lebel більше не згадується. Ніколи. Взагалі.\n"
            "Не тому що він поганий — а тому що я вже чую як ви закочуєте очі.\n"
            "Відтепер — тільки нові теми. Тільки новий біль.\n\n"
            "Аминь. \U0001f56f"
        ),
        "cron": "0 20 26 6 *",
    },
    {
        "prompt": (
            "Сьогодні вівторок. Нагадай групі перевірити щотижневі челенджі в грі Hunt: Showdown 1896."
            " Українською мовою. Пиши одразу повідомлення, без пояснень."
        ),
        "cron": "0 11 * * 1",
    },
    {
        "prompt": (
            "Сьогодні неділя, вже вечір."
            " Нагадай групі що скоро час грати в Hunt: Showdown 1896."
            " Українською мовою. Пиши одразу повідомлення, без пояснень."
        ),
        "cron": "0 21 * * 6",
    },
    {
        "prompt": _daily_prompt,   # callable -- resolved at send time with today's date
        "cron": "0 18 * * 0-4,6",
        "jitter": 10800,
    },
]
