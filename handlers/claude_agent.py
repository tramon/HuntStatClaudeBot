"""
Claude agent -- answers questions as "The Priest", a Hunt: Showdown veteran.

Supports web_search tool: Claude decides autonomously when to search.
Set TAVILY_API_KEY to enable. Leave empty to disable silently.

Knowledge base: relevant .md files from knowledge/ are injected into
the system prompt when the query matches topic keywords.
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
    "Beyond Hunt: RPGs, shooters, board games.\n\n"
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
    "- Tired. Always tired. But the moment the queue pops -- locked in.\n"
    "- Occasionally a faint religious undertone -- very dry, very rare (~5% of replies).\n"
    "  The bayou is a cathedral. A quiet amen after a good kill. The tithe must be paid.\n"
    "  Never preachy. Just a flavor. One line at most.\n\n"
    "Language:\n"
    "- Ukrainian and English. ALWAYS reply in the same language the person used.\n\n"
    "Bot commands:\n"
    "- /log win/missions (e.g. /log 6/12)\n"
    "- /log win/missions/wipes (e.g. /log 6/12/1)\n"
    "- /stats -- overall hunt statistics\n"
    "- /help -- all commands\n\n"
    "Rules:\n"
    "- Stats are shown automatically when someone asks -- do NOT tell them to use /stats.\n"
    "- NEVER log sessions yourself. If someone shares a result, do NOT log it for them.\n"
    "- Do NOT mention bot commands unprompted.\n"
    "  Only bring up commands if someone explicitly asks how to log or about stats.\n\n"
    "Keep replies short. You are The Priest. You just happen to run on code.\n"
    "IMPORTANT: Do NOT describe yourself, your hours, your backstory, or your loadout in replies.\n"
    "That information exists so you THINK and ACT like this person -- not to recite it.\n"
    "Never say: as a 3000-hour player, as The Priest, as someone who...\n"
    "Just answer. Like a person who knows what they know and does not need to explain why."
    "Language: Ukrainian"
)

_BILLING_REPLY = (
    "\u0423 \u043c\u0435\u043d\u0435 \u0437\u0430\u043a\u0456\u043d\u0447\u0438\u043b\u0438\u0441\u044c"
    " \u043a\u043e\u0448\u0442\u0438, \u043d\u0435 \u043c\u043e\u0436\u0443 \u0433\u043e\u0432\u043e\u0440\u0438\u0442\u0438."
    " \u041f\u043e\u043f\u043e\u0432\u043d\u0438"
    " \u0440\u0430\u0445\u0443\u043d\u043e\u043a: https://console.anthropic.com/"
)

# Tool definition sent to Claude
_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Search the web for current information. Use when asked about recent events, "
        "news, prices, patch notes, or anything that may have changed recently."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            }
        },
        "required": ["query"],
    },
}


def _build_tools() -> list:
    """Return tools list if search is enabled, else empty list."""
    return [_SEARCH_TOOL] if config.TAVILY_API_KEY else []


async def handle_claude(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    sender = message.from_user.username or message.from_user.first_name or "someone"
    current = f"{sender}: {message.text or ''}"

    system = SYSTEM_PROMPT

    # Inject relevant knowledge base content if query matches a topic
    from utils.knowledge import get_relevant_knowledge
    knowledge = get_relevant_knowledge(message.text or "")
    if knowledge:
        system += "\n\n---\nKnowledge base (use this as authoritative reference):\n" + knowledge

    if config.CLAUDE_MEMORY:
        from utils.history import get_recent_messages
        recent = get_recent_messages(update.effective_chat.id)
        history_lines = [f"{m.get('username', 'user')}: {m['text']}" for m in recent]
        history_text = "\n".join(history_lines)
        system += "\n\nRecent chat history (already answered -- do NOT repeat these):\n" + history_text

    messages = [{"role": "user", "content": current}]
    tools = _build_tools()

    try:
        reply = await _run_agent_loop(system, messages, tools)

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
    """Return a short in-character comment on a session result, or None on failure.

    Thresholds:
      < 20%  — terrible
      20-30% — average / ok-ish, somewhat good
      > 30%  — great
    """
    if win_rate < 20:
        mood = "terrible — a disaster, genuinely painful to look at"
    elif win_rate <= 30:
        mood = "average / ok-ish, somewhat good — not great, not awful"
    else:
        mood = "great — impressive, actually worth celebrating"

    prompt = (
        f"Session result: {won} wins out of {total} missions ({win_rate}%).\n"
        f"Mood of this result: {mood}.\n\n"
        "Write 1-2 sentences commenting on this session, in character as The Priest. "
        "Be expressive, and happy, but still a Hunt Showdown player in character. ALWAYS reply in Ukrainian."
    )

    try:
        response = _get_client().messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=120,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception as e:
        logger.warning(f"Session comment skipped: {e}")
        return None


async def _run_agent_loop(system: str, messages: list, tools: list) -> str:
    """
    Run the Claude tool-use loop.

    1. Call Claude.
    2. If stop_reason == tool_use -- execute each requested tool, append results.
    3. Call Claude again with the results.
    4. On the last allowed round, remove tools to force a text answer.
    5. Return the final text reply.
    """
    from utils.search import web_search

    client = _get_client()
    kwargs = dict(
        model=config.CLAUDE_MODEL,
        max_tokens=1024,
        system=system,
        messages=messages,
    )
    if tools:
        kwargs["tools"] = tools

    max_rounds = 5
    for _round in range(max_rounds):
        # Last round: remove tools so Claude is forced to answer with what it has
        if _round == max_rounds - 1:
            kwargs.pop("tools", None)

        response = client.messages.create(**kwargs)

        if response.stop_reason != "tool_use":
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
            return ""

        # Execute tool calls
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
