"""
Claude agent -- handles API calls and the tool-use loop.

Prompt building lives in system_prompt/ (persona.py, rules.py, builder.py).
Every Anthropic call goes through create_message(): the SDK call is synchronous,
so it runs in a worker thread and never blocks the Telegram event loop.
"""

import asyncio
import json
import logging

import anthropic
from telegram import Update
from telegram.ext import ContextTypes

import config
from system_prompt import SYSTEM_PROMPT, build_system_prompt
from system_prompt.builder import build_history_block
from utils.history import save_message
from utils.telegram_text import safe_reply

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=90.0, max_retries=3)
    return _client


async def create_message(**kwargs):
    """Non-blocking wrapper around client.messages.create."""
    return await asyncio.to_thread(_get_client().messages.create, **kwargs)


_BILLING_REPLY = (
    "У мене закінчились кошти, не можу говорити."
    " Поповни рахунок: https://console.anthropic.com/"
)

_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Search the web for current information: patch notes, new content, prices, the current meta, "
        "news, or anything that may have changed recently. Also use it for Hunt: Showdown 1896 facts "
        "when the knowledge base does not cover the question or may be outdated. "
        "Write the query in English, include 'Hunt Showdown 1896' and the year or patch number, "
        "and prefer official patch notes and huntshowdown.wiki.gg."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."}
        },
        "required": ["query"],
    },
}

_STATS_TOOL = {
    "name": "get_hunt_stats",
    "description": (
        "Get the group's logged Hunt: Showdown results from the Google Sheet: totals (sessions, "
        "missions, wins, win rate, server wipes) and the most recent sessions (date, won, total, "
        "win_pct, wipes). Use it for any question about how the group has been doing: win rate, "
        "best or worst session, trends, streaks. Never invent numbers."
    ),
    "input_schema": {"type": "object", "properties": {}, "required": []},
}


def _build_tools() -> list:
    tools = [_STATS_TOOL]
    if config.TAVILY_API_KEY:
        tools.append(_SEARCH_TOOL)
    return tools


def _stats_for_tool() -> str:
    from utils.sheets import SheetsError, get_all_sessions
    try:
        sessions = get_all_sessions()
    except SheetsError as e:
        return f"Stats unavailable: {e}"
    if not sessions:
        return "No sessions have been logged yet."
    won = sum(s["won"] for s in sessions)
    total = sum(s["total"] for s in sessions)
    wipes = sum(s["wipes"] for s in sessions)
    data = {
        "sessions": len(sessions),
        "missions": total,
        "wins": won,
        "win_rate_percent": round(won / total * 100, 1) if total else 0,
        "server_wipes": wipes,
        "recent_sessions": sessions[-40:],
    }
    return json.dumps(data, ensure_ascii=False)


async def _run_tool(name: str, args: dict) -> str:
    try:
        if name == "web_search":
            from utils.search import web_search
            query = (args or {}).get("query", "")
            logger.info(f"Web search: {query!r}")
            return (await asyncio.to_thread(web_search, query)) or "No results."
        if name == "get_hunt_stats":
            logger.info("Tool: get_hunt_stats")
            return await asyncio.to_thread(_stats_for_tool)
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        return f"Tool error: {e}"
    return f"Unknown tool: {name}"


def _quoted_context(message) -> str:
    """The message the user replied to, as a short context line ('' if none)."""
    quoted = message.reply_to_message
    if not quoted:
        return ""
    text = (quoted.text or quoted.caption or "").strip()
    if not text:
        return ""
    user = quoted.from_user
    if user and user.is_bot:
        who = "Прист" if user.username and user.username.lower() == config.BOT_USERNAME else (user.username or "bot")
    else:
        who = (user.username or user.first_name) if user else "someone"
    return f"[Replying to {who}: {text[:800]}]\n"


async def _keep_typing(bot, chat_id: int) -> None:
    """Telegram's typing indicator lasts ~5 s; refresh it while Claude is working."""
    try:
        while True:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass
    except Exception:
        pass


async def handle_claude(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    chat_id = update.effective_chat.id

    sender = message.from_user.username or message.from_user.first_name or "someone"
    text = message.text or ""
    quoted = _quoted_context(message)

    system = build_system_prompt(query=f"{text}\n{quoted}", chat_id=chat_id)
    history = build_history_block(chat_id, current_text=text)
    messages = [{"role": "user", "content": f"{history}{quoted}{sender}: {text}"}]

    typing = asyncio.create_task(_keep_typing(context.bot, chat_id))
    generated = False
    try:
        reply = await _run_agent_loop(system, messages, _build_tools())
        generated = True
    except anthropic.APIStatusError as e:
        logger.error(f"Anthropic API error {e.status_code}: {e}")
        err = str(e).lower()
        if e.status_code == 401 or "authentication" in err or "invalid x-api-key" in err:
            return
        elif e.status_code in (402, 529) or "credit" in err or "billing" in err:
            reply = _BILLING_REPLY
        elif e.status_code == 429:
            reply = "Забагато питань. Почекай."
        else:
            reply = f"API error ({e.status_code}). Try again later."
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        if "authentication" in str(e).lower() or "invalid x-api-key" in str(e).lower():
            return
        reply = "Cannot reach the API. Try again in a moment."
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        reply = "Something went wrong. Please try again."
    finally:
        typing.cancel()

    if not reply.strip():
        generated = False
        reply = "Відповідь вийшла порожньою. Спробуй сформулювати інакше."

    await safe_reply(message, reply)

    # Remember our own answer so follow-up questions have context.
    if generated and config.CLAUDE_MEMORY:
        save_message(chat_id, context.bot.id, config.BOT_DISPLAY_NAME, reply)


async def get_session_comment(won: int, total: int, win_rate: int) -> str | None:
    """Return a short comment on a session result, or None on failure."""
    if win_rate < 20:
        mood = "terrible -- a disaster, genuinely painful to look at"
    elif win_rate <= 30:
        mood = "average / ok-ish, somewhat good -- not great, not awful"
    else:
        mood = "great -- impressive, actually worth celebrating"

    prompt = (
        f"Session result: {won} wins out of {total} missions ({win_rate}%).\n"
        f"Mood of this result: {mood}.\n\n"
        "Comment on this session. "
        "Be dry, match the tone of a gaming group chat. ALWAYS reply in Ukrainian."
    )

    try:
        response = await create_message(
            model=config.CLAUDE_MODEL,
            max_tokens=600,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": config.CLAUDE_EFFORT},
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Session comment skipped: {e}")
        return None


def _extract_text(response) -> str:
    return "".join(
        block.text for block in response.content if getattr(block, "type", "") == "text"
    ).strip()


async def _run_agent_loop(system, messages: list, tools: list) -> str:
    """
    Run the Claude tool-use loop.

    1. Call Claude.
    2. If stop_reason == tool_use -- execute every requested tool, append results.
    3. Repeat up to max_rounds. On the last round tools are switched off (tool_choice none)
       to force a text answer.
    4. Return the final text reply.
    """
    kwargs = dict(
        model=config.CLAUDE_MODEL,
        max_tokens=4000,
        system=system,
        messages=list(messages),
        output_config={"effort": config.CLAUDE_EFFORT},
    )
    if tools:
        kwargs["tools"] = tools

    max_rounds = 5
    for _round in range(max_rounds):
        if tools and _round == max_rounds - 1:
            kwargs["tool_choice"] = {"type": "none"}

        response = await create_message(**kwargs)

        if response.stop_reason != "tool_use":
            return _extract_text(response)

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = await _run_tool(block.name, block.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })

        kwargs["messages"] = kwargs["messages"] + [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": tool_results},
        ]

    return ""
