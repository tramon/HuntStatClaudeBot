"""
Scheduled announcements config.

To add a new announcement -- add an entry to ANNOUNCEMENTS.
Messages are sent to ALL chats listed in ALLOWED_CHAT_IDS (from secrets/.env).

Cron format: "minute hour day_of_month month day_of_week"
  0 9 * * 1-5     -> 09:00 Mon-Fri
  0 17 * * 5      -> 17:00 every Friday
  0 10 * * 1      -> 10:00 every Monday
  0 9,18 * * *    -> 09:00 and 18:00 every day
  */30 * * * *    -> every 30 minutes

APScheduler day_of_week: 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun

Timezone: Europe/Kyiv

Each entry requires:
  "cron"   -- schedule
  "text"   -- static message (str or lambda () -> str)
  "prompt" -- let Claude generate the message (str instruction)
Only one of "text" or "prompt" is needed per entry.
"""

# =============================================================================
# ANNOUNCEMENTS
# =============================================================================

ANNOUNCEMENTS: list[dict] = [
    {
        "prompt": (
            "Сьогодні середа. Нагадай групі перевірити щотижневі челенджі в Hunt: Showdown. "
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
        "cron": "0 21 * * 6",   # 21:00 every Sunday (APScheduler: 6=Sun)
    },
    {
        "prompt": (
            "Поділись однією думкою про Hunt: Showdown 1896. "
            "Це може бути про трейт, зброю, тактику, компаунди, hunt showdown івенти, відомих hunt showdown стрімерів, мету, механіку або просто спостереження з байо. "
            "Вибери тему рандомно -- щоразу щось інше. "
            "2-3 речення, в характері The Priest. Українською. "
            "Без вступів типу 'до речі' або 'між іншим'."
        ),
        "cron": "0 20 * * 0-4,6",   # 21:00 Mon-Fri + Sun (skip Saturday)
    },
]
