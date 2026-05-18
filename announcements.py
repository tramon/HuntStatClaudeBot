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
  "text"   -- static message str or lambda () -> str
  "prompt" -- Claude generates the message from this instruction
  "jitter" -- random delay in seconds added to cron time (optional)
              e.g. jitter=10800 fires randomly within +3h of cron time
"""

# =============================================================================
# ANNOUNCEMENTS
# =============================================================================

ANNOUNCEMENTS: list[dict] = [
    {
        "prompt": (
            "Сьогодні середа. Нагадай групі перевірити щотижні челенджі в Hunt: Showdown. "
            "Декілька речень в характері The Priest. Українською."
        ),
        "cron": "0 11 * * 2",   # 11:00 every Wednesday
    },
    {
        "prompt": (
            "Сьогодні неділя, вже вечір. "
            "Нагадай групі що скоро час грати в Hunt: Showdown. "
            "Одне речення в характері The Priest. Українською."
        ),
        "cron": "0 21 * * 6",   # 21:00 every Sunday
    },
    {
        "prompt": (
            "Поділись однією думкою про Hunt: Showdown 1896. "
            "або задай питання філософського характеру. "
            "Тематика: трейт, зброя, тактики, білди, компаунди, івенти, стрімери, мета, механіка або байо. "
            "Вибери тему рандомно -- щораз щось інше. "
            "2-3 речення, в характері The Priest. Українською. "
            "Без вступів типу до речі або між іншим."
        ),
        "cron": "0 18 * * 0-4,6",   # base 18:00 Mon-Fri+Sun, fires 18:00-21:00
        "jitter": 10800,             # +0..3h random (10800s = 3h)
    },
]
