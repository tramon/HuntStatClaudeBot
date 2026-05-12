"""
Entry point -- registers handlers and starts polling.
"""

import asyncio
import logging
import sys

from telegram import BotCommand
from telegram.ext import Application, CallbackQueryHandler, ChatMemberHandler
from telegram.ext import CommandHandler, MessageHandler, filters

import config
from handlers.commands import cmd_log, cmd_stats, cmd_log_callback, menu_callback, cmd_help
from handlers.mention import handle_mention
from handlers.security import handle_new_chat_member

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)


async def post_init(app: Application) -> None:
    """Register the command menu that appears when users tap / in Telegram."""
    await app.bot.set_my_commands([
        BotCommand("log",   "Log a session result  (e.g. /log 6/12)"),
        BotCommand("stats", "Show overall hunt stats"),
        BotCommand("help",  "Show all available commands"),
    ])
    logger.info("Bot command menu registered")


def main() -> None:
    config.validate()

    if config.ALLOWED_CHAT_IDS:
        logger.info(f"Restricted to chat IDs: {config.ALLOWED_CHAT_IDS}")
    else:
        logger.warning("ALLOWED_CHAT_IDS not set -- bot will respond in any group")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    app.add_handler(ChatMemberHandler(handle_new_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))

    app.add_handler(CommandHandler("log",   cmd_log))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("help",  cmd_help))

    app.add_handler(CallbackQueryHandler(cmd_log_callback, pattern="^log_help$"))
    app.add_handler(CallbackQueryHandler(menu_callback,    pattern="^menu_"))

    # Group messages (only when bot is @mentioned)
    group_text = filters.TEXT & filters.ChatType.GROUPS & ~filters.COMMAND
    app.add_handler(MessageHandler(group_text, handle_mention))

    # Private messages (all text, no mention needed)
    private_text = filters.TEXT & filters.ChatType.PRIVATE & ~filters.COMMAND
    app.add_handler(MessageHandler(private_text, handle_mention))

    logger.info("Bot is running -- press Ctrl+C to stop")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
