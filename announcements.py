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
        # One-time joke -- fires once on 2026-06-26 at 20:00, repeats next year (remove after sending)
        "text": (
            "Офіційне повідомлення від The Priest.\n\n"
            "Lebel більше не згадується. Ніколи. Взагалі.\n"
            "Не тому що він поганий — а тому що я вже чую як ви закочуєте очі.\n"
            "Відтепер — тільки нові теми. Тільки новий біль.\n\n"
            "Аминь. 🕯"
        ),
        "cron": "0 20 26 6 *",   # 20:00 on June 26 -- fires once per year (remove after)
    },
    {
        "prompt": (
            "Сьогодні вівторок. Нагадай групі перевірити щотижневі челенджі в грі Hunt: Showdown 1896."
            " Декілька речень Українською мовою. Пиши одразу повідомлення, без пояснень."
        ),
        "cron": "0 11 * * 1",   # 11:00 every Tuesday
    },
    {
        "prompt": (
            "Сьогодні неділя, вже вечір."
            " Нагадай групі що скоро час грати в Hunt: Showdown 1896."
            " Одне речення Українською. Пиши одразу повідомлення, без пояснень."
        ),
        "cron": "0 21 * * 6",   # 21:00 every Sunday
    },
    {
        "prompt": (
            "Напиши одне коротке повідомлення в телеграм-групу мисливців Hunt: Showdown 1896.\n\n"
            "ПРАВИЛО 1 -- Не розкривай свій процес вибору теми. Жодних дужок, пояснень, кроків.\n"
            "Пиши одразу фінальне повідомлення.\n\n"
            "ПРАВИЛО 2 -- Вибір теми:\n"
            "Подивись на історію чату (передана вище як контекст).\n"
            "Якщо нещодавно обговорювали щось пов'язане з Hunt: Showdown — розвинь цю тему.\n"
            "Якщо ні — вибери одну з безпечних тем нижче (де не потрібно знати точних ігрових даних):\n"
            "  - Тактика або позиціювання на карті\n"
            "  - Механіка гри (темрява, звук, вогонь, отрута, відстань)\n"
            "  - Філософське питання до групи про стиль гри\n"
            "  - Порада яку всі знають але рідко кажуть вголос\n"
            "  - Боси: Butcher, Spider, Assassin, Scrapbeak (тільки загальні механіки, без точних цифр)\n\n"
            "ПРАВИЛО 3 -- Точні назви трейтів, зброї, мобів:\n"
            "Не вигадуй і не використовуй назви трейтів або зброї якщо не впевнений на 100%.\n"
            "Краще говори загально ('той трейт що дає броню', 'дробовик') ніж назвати неправильно.\n\n"
            "ПРАВИЛО 4 -- Мова і стиль:\n"
            "Українською. 2-3 речення. Без Lebel."
        ),
        "cron": "0 18 * * 0-4,6",   # base 18:00 Mon-Fri+Sun, fires 18:00-21:00
        "jitter": 10800,             # +0..3h random (10800s = 3h)
    },
]
