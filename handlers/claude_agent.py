"""
Claude agent -- handles API calls and tool-use loop.

Prompt building lives in persona/builder.py.
Character and rules live in persona/persona.py and persona/rules.py.
"""

import logging

import anthropic
from telegram import Update
from telegram.ext import ContextTypes

import config
from system_prompt import SYSTEM_PROMPT, build_system_prompt

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


_BILLING_REPLY = (
    "\u0423 \u043c\u0435\u043d\u0435 \u0437\u0430\u043a\u0456\u043d\u0447\u0438\u043b\u0438\u0441\u044c"
    " \u043a\u043e\u0448\u0442\u0438, \u043d\u0435 \u043c\u043e\u0436\u0443 \u0433\u043e\u0432\u043e\u0440\u0438\u0442\u0438."
    " \u041f\u043e\u043f\u043e\u0432\u043d\u0438"
    " \u0440\u0430\u0445\u0443\u043d\u043e\u043a: https://console.anthropic.com/"
)

_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Search the web for current information. Use when asked about recent events, "
        "news, prices, patch notes, or anything that may have changed recently. "
        "Also use for Hunt: Showdown game facts when no knowledge base is available."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The search query."}
        },
        "required": ["query"],
    },
}


def _build_tools() -> list:
    return [_SEARCH_TOOL] if config.TAVILY_API_KEY else []


async def handle_claude(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    sender = message.from_user.username or message.from_user.first_name or "someone"
    text = message.text or ""

    system = build_system_prompt(query=text, chat_id=update.effective_chat.id)
    messages = [{"role": "user", "content": f"{sender}: {text}"}]

    try:
        reply = await _run_agent_loop(system, messages, _build_tools())
    except anthropic.APIStatusError as e:
        logger.error(f"Anthropic API error {e.status_code}: {e}")
        err = str(e).lower()
        if e.status_code == 401 or "authentication" in err or "invalid x-api-key" in err:
            return
        elif e.status_code in (402, 529) or "credit" in err or "billing" in err:
            reply = _BILLING_REPLY
        elif e.status_code == 429:
            reply = "\u0417\u0430\u0431\u0430\u0433\u0430\u0442\u043e \u043f\u0438\u0442\u0430\u043d\u044c. \u041f\u043e\u0447\u0435\u043a\u0430\u0439."
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
        "Write 1-2 sentences commenting on this session. "
        "Be dry, brief, match the tone of a gaming group chat. ALWAYS reply in Ukrainian."
    )

    try:
        response = _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=120,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": config.CLAUDE_EFFORT},
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Session comment skipped: {e}")
        return None


async def _run_agent_loop(system: str, messages: list, tools: list) -> str:
    """
    Run the Claude tool-use loop.

    1. Call Claude.
    2. If stop_reason == tool_use -- execute tools, append results.
    3. Repeat up to max_rounds. On the last round remove tools to force a text answer.
    4. Return the final text reply.
    """
    from utils.search import web_search

    client = _get_client()
    kwargs = dict(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        system=system,
        messages=messages,
        output_config={"effort": config.CLAUDE_EFFORT},
    )
    if tools:
        kwargs["tools"] = tools

    max_rounds = 5
    for _round in range(max_rounds):
        if _round == max_rounds - 1:
            kwargs.pop("tools", None)

        response = client.messages.create(**kwargs)

        if response.stop_reason != "tool_use":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "web_search":
                query = block.input.get("query", "")
                logger.info(f"Web search: {query!r}")
                result = web_search(query)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result or "No results.",
                })

        kwargs["messages"] = kwargs["messages"] + [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": tool_results},
        ]

    return ""
