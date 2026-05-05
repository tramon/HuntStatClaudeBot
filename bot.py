"""
Entry point — registers handlers and starts polling.
"""

import asyncio
import logging

from telegram import BotCommand
from telegram.ext import Application, ChatMemberHandler, CommandHandler, MessageHandler, filters

import config
from handlers.commands import cmd_log, cmd_stats, cmd_log_callback, menu_callback
from handlers.mention import handle_mention
from handlers.security import handle_new_chat_member

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    """Register the command menu that appears when users tap / in Telegram."""
    await app.bot.set_my_commands([
        BotCommand("log",   "Log a session result  (e.g. /log 6/12)"),
        BotCommand("stats", "Show overall hunt stats"),
    ])
    logger.info("Bot command menu registered")


def main() -> None:
    # Validate env variables before doing anything else
    config.validate()

    if config.ALLOWED_CHAT_IDS:
        logger.info(f"Restricted to chat IDs: {config.ALLOWED_CHAT_IDS}")
    else:
        logger.warning("ALLOWED_CHAT_IDS not set — bot will respond in any group")

    # Python 3.10+ no longer auto-creates an event loop — set one explicitly
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    # Leave any group not on the whitelist
    app.add_handler(
        ChatMemberHandler(handle_new_chat_member, ChatMemberHandler.MY_CHAT_MEMBER)
    )

    # Slash commands — work without Claude
    app.add_handler(CommandHandler("log",   cmd_log))
    app.add_handler(CommandHandler("stats", cmd_stats))

    # Inline button callbacks
    from telegram.ext import CallbackQueryHandler
    app.add_handler(CallbackQueryHandler(cmd_log_callback, pattern="^log_help$"))
    app.add_handler(CallbackQueryHandler(menu_callback,    pattern="^menu_"))

    # Handle all non-command text messages in groups
    app.add_handler(
        MessageHandler(filters.TEXT & filters.ChatType.GROUPS & ~filters.COMMAND, handle_mention)
    )

    logger.info("Bot is running — press Ctrl+C to stop")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
