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
            "Сьогодні вівторок. Нагадай групі перевірити щотижневі челенджі в грі Hunt: Showdown 1896 ."
            "Обов'язково перевір @/knowledge бази знань, якщо будеш використовувати пов'язану інформацію"
            "Декілька речень Українською мовою"
        ),
        "cron": "0 11 * * 1",   # 11:00 every Tuesday
    },
    {
        "prompt": (
            "Сьогодні неділя, вже вечір. "
            "Нагадай групі що скоро час грати в Hunt: Showdown 1896 ."
            "Обов'язково перевір @/knowledge бази знань, якщо будеш використовувати пов'язану інформацію"
            "приблизно одне речення Українською мовою"
        ),
        "cron": "0 21 * * 6",   # 21:00 every Sunday
    },
    {
        "prompt": (
            "Поділись однією думкою про гру `Hunt: Showdown 1896`. "
            "Обов'язково перевір @/knowledge бази знань, якщо будеш використовувати пов'язану інформацію"
            "або задай питання філософського характеру. "
            "Тематика: трейт, зброя, тактики, білди, компаунди, івенти, стрімери, мета, механіка або байо, або інші що стосуються гри або минулих повідомлень з чату"
            "Декілька речень Українською мовою"
        ),
        "cron": "0 18 * * 0-4,6",   # base 18:00 Mon-Fri+Sun, fires 18:00-21:00
        "jitter": 10800,             # +0..3h random (10800s = 3h)
    },
]
