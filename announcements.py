"""
Scheduled announcements config.

To add a new announcement -- add an entry to ANNOUNCEMENTS.
Messages are sent to ALL chats listed in ALLOWED_CHAT_IDS (from secrets/.env).

Cron format: "minute hour day_of_month month day_of_week"
  0 9 * * 1-5     → 09:00 Mon-Fri
  0 17 * * 5      → 17:00 every Friday
  0 10 * * 1      → 10:00 every Monday
  0 9,18 * * *    → 09:00 and 18:00 every day
  */30 * * * *    → every 30 minutes

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
            "декілька речень в характері The Priest. Українською."
        ),
        "cron": "0 11 * * 3",   # 11:00 every Wednesday
    },
    {
        "prompt": (
            "Сьогодні Неділя. Вже вечір. Нагадай групі нагадай групі, що скоро грати в Hunt: Showdown. "
            "одне речення в характері The Priest. Українською."
            "Приклад: Ей, хлопці, то ми сьогодні граємо чи ні?"
        ),
        "cron": "0 21 * * 7",   # 21:00 every Sunday
    },
]
