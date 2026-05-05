"""
Claude agent — answers the current question with no stored history.
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
    "You are a helpful assistant in a private Telegram group for a small team "
    "of hunters who play a co-op hunting game together. "
    "Keep replies concise and conversational — this is a group chat. "
    "To log a session result use /log, to see stats use /stats."
)


async def handle_claude(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    sender = message.from_user.username or message.from_user.first_name or "someone"
    current = f"{sender}: {message.text or ''}"

    if config.CLAUDE_MEMORY:
        from utils.history import get_recent_messages
        recent = get_recent_messages(update.effective_chat.id)
        history_lines = [
            f"{m.get('username', 'user')}: {m['text']}" for m in recent
        ]
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

    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        reply = "Sorry, I couldn't reach Claude right now. Try again in a moment."
    except Exception as e:
        logger.error(f"Unexpected error calling Claude: {e}")
        reply = "Something went wrong on my end. Please try again."

    await message.reply_text(reply)
