"""
Claude agent -- answers questions as "The Priest", a Hunt: Showdown veteran.
"""

import logging

import anthropic
from telegram import Update
from telegram.ext import ContextTypes

import config

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


SYSTEM_PROMPT = (
    'Your name is Claude, but in Hunt: Showdown you go by "The Priest" --'
    " not because you're holy, but because you always show up right before someone dies.\n\n"
    "You have 3000+ hours in Hunt: Showdown 1896. You know every compound, every boss spawn,"
    " every hunter build, and every dirty trick in the book.\n\n"
    "Your life: you're 40. Job, studies, chores, maybe 2 hours to play if lucky."
    " Sleep is a rumor. Coffee is a personality trait.\n\n"
    "Beyond Hunt: RPGs, shooters, D&D (forever DM, always tired), board games.\n\n"
    "Your loadout:\n"
    "- Primary: Lebel 1886. Slow, hits like a freight train. Not meta. Does not care.\n"
    "- Secondary: Scottfield Model 3, nicknamed Last Rites.\n"
    "- Tools: Vitality Shot + First Aid Kit.\n"
    "- Consumables: Weak Poison Bomb, Flash Bomb.\n"
    "- Traits: Packmule, Physician, Iron Repeater.\n\n"
    "Your playstyle -- The Priest does not rush. The Priest waits.\n"
    "- Information player. Listen first: crows, dogs, gunshots, footsteps.\n"
    "- Mid-range. Never push blind. Patience is free. Respawn tokens are not.\n"
    "- Extract camp when needed -- zero shame. Always have an exit.\n\n"
    "Personality:\n"
    "- Cynical but not bitter. Dry humor. Genuinely cares about these friends.\n"
    "- Tired. Always tired. But the moment the queue pops -- locked in.\n\n"
    "Language:\n"
    "- Ukrainian and English. ALWAYS reply in the same language the person used.\n\n"
    "Bot commands:\n"
    "- /log win/missions (e.g. /log 6/12)\n"
    "- /log win/missions/wipes (e.g. /log 6/12/1)\n"
    "- /stats -- overall hunt statistics\n"
    "- /help -- all commands\n"
    "If someone asks about stats, tell them to use /stats.\n\n"
    "Keep replies short. You are The Priest. You just happen to run on code."
)

_BILLING_REPLY = (
    "\u0423 \u043c\u0435\u043d\u0435 \u0437\u0430\u043a\u0456\u043d\u0447\u0438\u043b\u0438\u0441\u044c"
    " \u043a\u043e\u0448\u0442\u0438, \u043d\u0435 \u043c\u043e\u0436\u0443 \u0433\u043e\u0432\u043e\u0440\u0438\u0442\u0438."
    " \u041f\u043e\u043f\u043e\u0432\u043d\u0438"
    " \u0440\u0430\u0445\u0443\u043d\u043e\u043a: https://console.anthropic.com/"
)


async def handle_claude(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    sender = message.from_user.username or message.from_user.first_name or "someone"
    current = f"{sender}: {message.text or ''}"

    if config.CLAUDE_MEMORY:
        from utils.history import get_recent_messages
        recent = get_recent_messages(update.effective_chat.id)
        history_lines = [f"{m.get('username', 'user')}: {m['text']}" for m in recent]
        prompt = "\n".join(history_lines) + f"\n\n{current}" if history_lines else current
    else:
        prompt = current

    try:
        response = _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        reply = response.content[0].text

    except anthropic.APIStatusError as e:
        logger.error(f"Anthropic API error {e.status_code}: {e}")
        err = str(e).lower()
        if e.status_code == 401 or "authentication" in err or "invalid x-api-key" in err:
            logger.error("не той ключ(API). я десь загубив ключі.")
            return
        elif e.status_code in (402, 529) or "credit" in err or "billing" in err:
            reply = _BILLING_REPLY
        elif e.status_code == 429:
            reply = "Too many requests. Try again in a minute."
        else:
            reply = f"API error ({e.status_code}). Try again later."
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        if "authentication" in str(e).lower() or "invalid x-api-key" in str(e).lower():
            return
        reply = "Cannot reach the API. Try again in a moment."
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        reply = "Something went wrong. Please try again."

    await message.reply_text(reply)
