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
  "jitter" -- random delay in seconds added to cron time (optional)
"""

import random
from datetime import datetime

# =============================================================================
# DAILY TOPIC PICKER
# Seeded by current datetime with milliseconds -- each fire gets a
# unique seed, so topics are effectively random on every announcement.
# =============================================================================

_TOPICS = [
    ("тактика",      "Тактика або позиціювання на карті під час полювання"),
    ("звук",         "Механіка звуку в грі -- кроки, постріли, ворони, собаки"),
    ("темрява",      "Механіка темряви та ліхтарів"),
    ("вогонь",       "Вогонь і отрута як інструменти контролю"),
    ("боси",         "Боси байо: Butcher, Spider, Assassin або Scrapbeak -- загальні механіки та поведінка"),
    ("моби",         "Моби байо -- Grunt, Hellhound, Armored та інші"),
    ("екстракція",   "Тактика екстракції -- коли відступати і як"),
    ("позиція",      "Важливість позиціонування та укриттів"),
    ("командна гра", "Командна гра та комунікація в дуо/тріо"),
    ("білд",         "Баланс між зброєю, інструментами та витратниками"),
    ("мета",         "Що зараз у меті і чому це не завжди правильно"),
    ("філософія",    "Філософське питання до групи про стиль гри або ментальність мисливця"),
    ("порада",       "Порада яку всі знають але рідко практикують"),
    ("карта",        "Читання карти та розуміння де зараз небезпечно"),
    ("патрони",      "Типи патронів та коли що використовувати"),
]


def _daily_topic() -> tuple[str, str]:
    """Return (key, description) seeded by current date+time with milliseconds.

    Millisecond precision means each announcement fire gets a unique seed,
    so topics rotate randomly on every run.
    """
    seed = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
    rng = random.Random(seed)
    return rng.choice(_TOPICS)


def _daily_prompt() -> str:
    """Build the daily announcement prompt with a date-seeded topic."""
    key, topic = _daily_topic()
    return (
        f"Напиши одне коротке повідомлення в телеграм-групу мисливців Hunt: Showdown 1896.\n\n"
        f"ТЕМА СЬОГОДНІ: {topic}\n\n"
        "ПРАВИЛО 1 -- Не розкривай назву теми і не коментуй вибір. Пиши одразу повідомлення.\n\n"
        "ПРАВИЛО 2 -- Якщо в чаті (контекст вище) нещодавно обговорювали саме цю тему або щось близьке -- "
        "розвинь розмову замість шаблонного факту.\n\n"
        "ПРАВИЛО 3 -- Для будь-яких конкретних назв (трейти, зброя, моби) використовуй ТІЛЬКИ knowledge base. "
        "Якщо knowledge base не покриває деталь -- говори загально.\n\n"
        "ПРАВИЛО 4 -- Українською. 2-3 речення. Без Lebel."
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
            " Декілька речень Українською мовою. Пиши одразу повідомлення, без пояснень."
        ),
        "cron": "0 11 * * 1",
    },
    {
        "prompt": (
            "Сьогодні неділя, вже вечір."
            " Нагадай групі що скоро час грати в Hunt: Showdown 1896."
            " Одне речення Українською. Пиши одразу повідомлення, без пояснень."
        ),
        "cron": "0 21 * * 6",
    },
    {
        "prompt": _daily_prompt,   # callable -- resolved at send time with today's date
        "cron": "0 18 * * 0-4,6",
        "jitter": 10800,
    },
]
