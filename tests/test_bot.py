"""
Offline tests: no Telegram, no Anthropic, no Google. Run:  python -m pytest tests -q
"""
import asyncio
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("BOT_TOKEN", "x")
os.environ.setdefault("ANTHROPIC_API_KEY", "x")

import config
from handlers import claude_agent, mention
from system_prompt.builder import build_history_block, build_system_prompt, build_announcement_prompt
from utils.knowledge import get_relevant_knowledge
from utils.telegram_text import format_reply, split_message, safe_reply


# ---------- config ----------
def test_empty_env_counts_as_unset(monkeypatch):
    monkeypatch.setenv("CONTEXT_MESSAGES", "")
    assert config._env("CONTEXT_MESSAGES", "15") == "15"
    monkeypatch.setenv("CONTEXT_MESSAGES", " 7 ")
    assert config._env("CONTEXT_MESSAGES", "15") == "7"


# ---------- formatting ----------
def test_format_reply():
    out = format_reply("## Заголовок\n**Berthier** це `Size 3` & <b>тест</b>")
    assert "##" not in out
    assert "<b>Berthier</b>" in out and "<code>Size 3</code>" in out
    assert "&amp;" in out and "&lt;b&gt;" in out


def test_split_message_limits_and_keeps_content():
    text = "\n\n".join(f"Абзац {i} " + "слово " * 120 for i in range(30))
    chunks = split_message(text, limit=1000)
    assert len(chunks) > 1 and all(len(c) <= 1000 for c in chunks)
    assert "".join(c.replace("\n", "").replace(" ", "") for c in chunks) == text.replace("\n", "").replace(" ", "")
    assert split_message("   ") == []


# ---------- stats intent ----------
def test_stats_intent_no_false_positives():
    assert mention._has_stats_intent("статистика")
    assert mention._has_stats_intent("покажи стату")
    assert mention._has_stats_intent("скільки перемог")
    assert mention._has_stats_intent("stats")
    assert not mention._has_stats_intent("достатньо добре")
    assert not mention._has_stats_intent("який статус у сервера")
    assert not mention._has_stats_intent("який результат патча 2.9 і що змінилось у зброї для дробовиків")


# ---------- knowledge routing ----------
def test_knowledge_routing():
    assert "Bloodskin" in get_relevant_knowledge("як вбити bloodskin?")
    assert "Bloodskin" in get_relevant_knowledge("який новий бос?")
    assert "Size" in get_relevant_knowledge("скільки слотів у Berthier")
    assert "Siphon" in get_relevant_knowledge("що робить трейт siphon")
    assert get_relevant_knowledge("привіт, як справи") == ""


# ---------- system prompt ----------
def test_system_prompt_blocks():
    blocks = build_system_prompt(query="bloodskin")
    assert isinstance(blocks, list) and blocks[0]["type"] == "text"
    kb = [b for b in blocks if "cache_control" in b]
    assert len(kb) == 1 and "ADDITIONAL REFERENCE" in kb[0]["text"]
    assert "Current date and time" in blocks[-1]["text"]
    assert not any("cache_control" in b for b in build_system_prompt(query="привіт"))
    ann = build_announcement_prompt("a: b")
    assert any("ОСТАННІ ПОВІДОМЛЕННЯ" in b["text"] for b in ann)


def test_history_block_drops_current_message(monkeypatch):
    monkeypatch.setattr(config, "CLAUDE_MEMORY", True)
    import utils.history as h
    monkeypatch.setattr(h, "get_recent_messages", lambda chat_id, limit=None: [
        {"username": "a", "text": "старе"}, {"username": "b", "text": "поточне"}])
    block = build_history_block(1, current_text="поточне")
    assert "a: старе" in block and "поточне" not in block
    monkeypatch.setattr(config, "CLAUDE_MEMORY", False)
    assert build_history_block(1, "x") == ""


# ---------- agent loop ----------
def _resp(stop, *blocks):
    return types.SimpleNamespace(stop_reason=stop, content=list(blocks))

def _text(t):
    return types.SimpleNamespace(type="text", text=t)

def _tool(name, id_="t1", **inp):
    return types.SimpleNamespace(type="tool_use", name=name, id=id_, input=inp)


def test_agent_loop_runs_tool_then_answers(monkeypatch):
    calls = []
    async def fake_create(**kw):
        calls.append(kw)
        if len(calls) == 1:
            return _resp("tool_use", _tool("get_hunt_stats"))
        return _resp("end_turn", _text("Winrate 25%"))
    monkeypatch.setattr(claude_agent, "create_message", fake_create)
    monkeypatch.setattr(claude_agent, "_stats_for_tool", lambda: '{"wins": 3}')
    out = asyncio.run(claude_agent._run_agent_loop([{"type": "text", "text": "s"}], [{"role": "user", "content": "q"}], claude_agent._build_tools()))
    assert out == "Winrate 25%"
    last_user = calls[1]["messages"][-1]
    assert last_user["content"][0]["type"] == "tool_result" and "wins" in last_user["content"][0]["content"]


def test_agent_loop_unknown_tool_and_last_round_forced_text(monkeypatch):
    n = {"i": 0}
    async def fake_create(**kw):
        n["i"] += 1
        if kw.get("tool_choice") == {"type": "none"}:
            return _resp("end_turn", _text("done"))
        return _resp("tool_use", _tool("nope", id_=f"t{n['i']}"))
    monkeypatch.setattr(claude_agent, "create_message", fake_create)
    out = asyncio.run(claude_agent._run_agent_loop("s", [{"role": "user", "content": "q"}], claude_agent._build_tools()))
    assert out == "done" and n["i"] == 5


# ---------- full handler flow with fakes ----------
class FakeMsg:
    def __init__(self, text, reply_to=None, user_id=7, username="andrii", is_bot=False):
        self.text = text; self.caption = None; self.reply_to_message = reply_to
        self.from_user = types.SimpleNamespace(id=user_id, username=username, first_name=username, is_bot=is_bot)
        self.sent = []
    async def reply_text(self, text, parse_mode=None, reply_markup=None):
        self.sent.append((text, parse_mode)); return self


class FakeBot:
    id = 999
    async def send_chat_action(self, **kw): pass


def _update(msg):
    return types.SimpleNamespace(message=msg, effective_chat=types.SimpleNamespace(id=-100, type="supergroup"))


def test_handle_claude_includes_reply_context_and_formats(monkeypatch):
    seen = {}
    async def fake_create(**kw):
        seen.update(kw)
        return _resp("end_turn", _text("**Берtier** норм & тихий"))
    monkeypatch.setattr(claude_agent, "create_message", fake_create)
    monkeypatch.setattr(config, "CLAUDE_MEMORY", False)
    quoted = FakeMsg("Berthier чи Mosin?", username="vasyl")
    msg = FakeMsg("@HuntStatClaudeBot а який швидший?", reply_to=quoted)
    ctx = types.SimpleNamespace(bot=FakeBot())
    asyncio.run(claude_agent.handle_claude(_update(msg), ctx))
    content = seen["messages"][0]["content"]
    assert "Replying to vasyl: Berthier чи Mosin?" in content and "andrii: @HuntStatClaudeBot" in content
    assert any("cache_control" in b for b in seen["system"])  # KB matched via the quoted text
    assert msg.sent and msg.sent[0][1] == "HTML" and "<b>" in msg.sent[0][0] and "&amp;" in msg.sent[0][0]


def test_empty_model_answer_gets_fallback(monkeypatch):
    async def fake_create(**kw): return _resp("end_turn")
    monkeypatch.setattr(claude_agent, "create_message", fake_create)
    msg = FakeMsg("щось"); ctx = types.SimpleNamespace(bot=FakeBot())
    asyncio.run(claude_agent.handle_claude(_update(msg), ctx))
    assert "порожньою" in msg.sent[0][0]


def test_reply_to_bot_triggers_without_mention(monkeypatch):
    called = {}
    async def fake_handle(update, context): called["yes"] = True
    monkeypatch.setattr(mention, "handle_claude", fake_handle)
    monkeypatch.setattr(config, "CLAUDE_MEMORY", False)
    monkeypatch.setattr(config, "ALLOWED_CHAT_IDS", [])
    ctx = types.SimpleNamespace(bot=FakeBot())
    bot_msg = FakeMsg("відповідь бота", user_id=999, is_bot=True)
    asyncio.run(mention.handle_mention(_update(FakeMsg("а чому так?", reply_to=bot_msg)), ctx))
    assert called.get("yes")
    called.clear()
    asyncio.run(mention.handle_mention(_update(FakeMsg("просто чат між своїми")), ctx))
    assert not called


# ---------- announcements: stateless, date-derived randomness ----------
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import announcements
from apscheduler.triggers.cron import CronTrigger
from utils.scheduler import DateJitterTrigger

_KYIV = ZoneInfo("Europe/Kyiv")


def test_topic_is_deterministic_and_does_not_repeat_within_cycle():
    day0 = datetime(2026, 11, 16, 18, 5, tzinfo=_KYIV)
    assert announcements.pick_topic(day0) == announcements.pick_topic(day0)  # same moment -> same pick (restart-safe)
    n = len(announcements._TOPICS)
    start = datetime(2026, 1, 1, 18, 0, tzinfo=_KYIV)
    topics = [announcements.pick_topic(start + timedelta(days=i))[0] for i in range(n * 3)]
    for i in range(0, n * 3 - n + 1):
        pass
    # consecutive days never repeat, and every full cycle visits all topics exactly once
    assert all(topics[i] != topics[i + 1] for i in range(len(topics) - 1))
    ordinals = [(start + timedelta(days=i)).date().toordinal() // n for i in range(n * 3)]
    for cycle in set(ordinals):
        chunk = [t for t, c in zip(topics, ordinals) if c == cycle]
        if len(chunk) == n:
            assert len(set(chunk)) == n


def test_topics_are_not_advice():
    for t in announcements._TOPICS:
        assert "порад" not in t.lower()
    prompt = announcements._daily_prompt()
    assert "НІЯКИХ порад" in prompt


def test_date_jitter_is_stable_across_restarts():
    cron = CronTrigger(minute="0", hour="18", timezone="Europe/Kyiv")
    trig = DateJitterTrigger(cron, 10800, salt="a-3")
    day = datetime(2026, 11, 16, tzinfo=_KYIV)
    # the "restart" can happen at any time: the fire time of that day is always the same
    fires = {trig.get_next_fire_time(None, day + timedelta(hours=h)) for h in (0, 6, 12, 17, 17.9)}
    assert len(fires) == 1
    fire = fires.pop()
    assert fire.date() == day.date() and 18 <= fire.hour < 21
    # before it fires -> still today; after it fired -> tomorrow, never the same moment twice
    nxt = trig.get_next_fire_time(fire, fire + timedelta(seconds=1))
    assert nxt.date() == (day + timedelta(days=1)).date()
    assert trig.get_next_fire_time(None, fire + timedelta(minutes=30)).date() == nxt.date()
    # a different day gets a different offset
    offsets = {(trig._fire_time(day + timedelta(days=d, hours=18)) - (day + timedelta(days=d, hours=18))) for d in range(10)}
    assert len(offsets) > 1


def test_persona_has_no_advice_giving():
    from system_prompt import SYSTEM_PROMPT
    low = SYSTEM_PROMPT.lower()
    assert "never give advice" in low and "free to share opinions, builds, and advice" not in low
    assert "verdict" not in low


# ---------- bot heartbeat ----------
def test_heartbeat_exits_after_repeated_failures(monkeypatch):
    import bot as botmod

    class DeadBot:
        async def get_me(self):
            raise RuntimeError("no network")

    app = types.SimpleNamespace(bot=DeadBot(), updater=types.SimpleNamespace(running=True))
    monkeypatch.setattr(botmod, "_HEARTBEAT_EVERY", 0)
    monkeypatch.setattr(botmod, "_HEARTBEAT_MAX_FAILS", 3)
    codes = []

    def fake_exit(code):
        codes.append(code)
        raise SystemExit(code)

    monkeypatch.setattr(botmod.os, "_exit", fake_exit)
    try:
        asyncio.run(botmod._heartbeat(app))
    except SystemExit:
        pass
    assert codes == [1]


def test_heartbeat_stays_quiet_when_healthy(monkeypatch):
    import bot as botmod

    class OkBot:
        calls = 0
        async def get_me(self):
            OkBot.calls += 1
            if OkBot.calls >= 4:
                raise asyncio.CancelledError()

    app = types.SimpleNamespace(bot=OkBot(), updater=types.SimpleNamespace(running=True))
    monkeypatch.setattr(botmod, "_HEARTBEAT_EVERY", 0)
    monkeypatch.setattr(botmod.os, "_exit", lambda c: (_ for _ in ()).throw(AssertionError("must not exit")))
    try:
        asyncio.run(botmod._heartbeat(app))
    except (asyncio.CancelledError, BaseException) as e:
        assert not isinstance(e, AssertionError)
