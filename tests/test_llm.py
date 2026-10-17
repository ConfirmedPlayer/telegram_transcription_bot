import asyncio

import anthropic
import httpx2
import openai
from aiohttp import web
from aiohttp.test_utils import TestServer

from services.llm import Provider, call_anthropic, complete, strip_think

PRIMARY = Provider("https://api.cerebras.ai/v1", "key-1", "qwen-3.8-27b")
FALLBACK = Provider("https://api.groq.com/openai/v1", "key-2", "qwen/qwen3.8-27b")
MESSAGES = [{"role": "user", "content": "привет"}]


def auth_error() -> openai.AuthenticationError:
    request = httpx2.Request("POST", "https://api.cerebras.ai/v1/chat/completions")
    return openai.AuthenticationError("Wrong API Key", response=httpx2.Response(401, request=request), body=None)


class FakeCall:
    """Подменяет сетевой вызов: по ответу/исключению на каждый провайдер."""

    def __init__(self, **by_host):
        self.by_host = by_host
        self.calls = []

    async def __call__(self, provider, messages, max_tokens, timeout):
        self.calls.append(provider.name)
        outcome = self.by_host[provider.name]
        if isinstance(outcome, BaseException):
            raise outcome
        if callable(outcome):
            return await outcome()
        return outcome


def test_provider_name_is_host():
    assert PRIMARY.name == "api.cerebras.ai"


def test_strip_think_removes_leading_block():
    assert strip_think("<think>рассуждаю</think>\nИтог") == "Итог"
    assert strip_think("Просто ответ") == "Просто ответ"


def test_strip_think_unclosed_block_is_empty():
    assert strip_think("<think>не успел закончить") == ""
    assert strip_think(None) == ""


async def test_primary_answers(clock):
    call = FakeCall(**{"api.cerebras.ai": "Сводка"})
    result = await complete(MESSAGES, [PRIMARY, FALLBACK], clock() + 15, 350, call=call, clock=clock)
    assert result == ("Сводка", "api.cerebras.ai")
    assert call.calls == ["api.cerebras.ai"]


async def test_error_falls_back_exactly_once(clock):
    call = FakeCall(**{"api.cerebras.ai": RuntimeError("503"), "api.groq.com": "Резерв"})
    result = await complete(MESSAGES, [PRIMARY, FALLBACK], clock() + 15, 350, call=call, clock=clock)
    assert result == ("Резерв", "api.groq.com")
    assert call.calls == ["api.cerebras.ai", "api.groq.com"]


async def test_auth_error_is_logged_as_error(clock, log_records):
    call = FakeCall(**{"api.cerebras.ai": auth_error(), "api.groq.com": "Резерв"})
    result = await complete(MESSAGES, [PRIMARY, FALLBACK], clock() + 15, 350, call=call, clock=clock)
    assert result == ("Резерв", "api.groq.com")
    errors = [text for level, text in log_records if level == "ERROR"]
    assert any("api.cerebras.ai" in text and "ключ" in text for text in errors)


async def test_empty_answer_counts_as_failure(clock):
    call = FakeCall(**{"api.cerebras.ai": "<think>…</think>", "api.groq.com": "Резерв"})
    result = await complete(MESSAGES, [PRIMARY, FALLBACK], clock() + 15, 350, call=call, clock=clock)
    assert result == ("Резерв", "api.groq.com")


async def test_both_fail_returns_none(clock):
    call = FakeCall(**{"api.cerebras.ai": RuntimeError("x"), "api.groq.com": RuntimeError("y")})
    assert await complete(MESSAGES, [PRIMARY, FALLBACK], clock() + 15, 350, call=call, clock=clock) is None


async def test_provider_without_key_is_skipped(clock):
    call = FakeCall(**{"api.groq.com": "Резерв"})
    no_key = Provider("https://api.cerebras.ai/v1", "", "qwen-3.8-27b")
    result = await complete(MESSAGES, [no_key, FALLBACK], clock() + 15, 350, call=call, clock=clock)
    assert result == ("Резерв", "api.groq.com")
    assert call.calls == ["api.groq.com"]


async def test_no_attempt_when_deadline_too_close(clock):
    call = FakeCall(**{"api.cerebras.ai": "Сводка"})
    assert await complete(MESSAGES, [PRIMARY], clock() + 1.0, 350, call=call, clock=clock) is None
    assert call.calls == []


async def test_slow_provider_is_cut_by_deadline():
    async def slow():
        await asyncio.sleep(5)
        return "поздно"

    call = FakeCall(**{"api.cerebras.ai": slow, "api.groq.com": "Резерв"})
    loop = asyncio.get_running_loop()
    started = loop.time()
    result = await complete(MESSAGES, [PRIMARY, FALLBACK], loop.time() + 0.2, 350,
                            call=call, clock=loop.time, min_attempt=0.05)
    assert result is None  # на резерв времени уже не осталось
    assert loop.time() - started < 1.0


# --- Claude через родной API Anthropic ---

CLAUDE = Provider("https://api.anthropic.com", "sk-ant-test", "claude-opus-5-5", {"output_config": {"effort": "low"}})


def claude_reply(stop_reason="end_turn"):
    return {
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [
            {"type": "thinking", "thinking": "", "signature": "sig"},
            {"type": "text", "text": "Сводка"},
        ],
        "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


async def call_claude_locally(reply):
    """Вызвать Claude через локальный сервер вместо api.anthropic.com; вернуть ответ, тело и заголовки запроса."""
    seen = {}

    async def messages(request):
        seen["path"] = request.path
        seen["body"] = await request.json()
        seen["api_key"] = request.headers.get("x-api-key")
        return web.json_response(reply)

    app = web.Application()
    app.router.add_post("/v1/messages", messages)
    async with TestServer(app) as server:
        local = Provider(str(server.make_url("")), CLAUDE.api_key, CLAUDE.model, CLAUDE.extra)
        text = await call_anthropic(local, MESSAGES, 350, 5.0)
    return text, seen


def test_anthropic_provider_is_recognised_by_host():
    assert CLAUDE.is_anthropic
    assert not FALLBACK.is_anthropic


async def test_claude_answer_is_only_text_without_thinking():
    text, seen = await call_claude_locally(claude_reply())
    assert text == "Сводка"
    assert seen["path"] == "/v1/messages"
    assert seen["api_key"] == "sk-ant-test"
    assert seen["body"]["model"] == "claude-opus-5-5"
    assert seen["body"]["output_config"] == {"effort": "low"}


async def test_claude_gets_room_for_thinking_beyond_summary_limit():
    _, seen = await call_claude_locally(claude_reply())
    assert seen["body"]["max_tokens"] > 350


async def test_claude_refusal_is_empty_answer():
    text, _ = await call_claude_locally(claude_reply(stop_reason="refusal"))
    assert text == ""


async def test_claude_auth_error_is_logged_as_error(clock, log_records):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.AuthenticationError("invalid x-api-key", response=httpx2.Response(401, request=request), body=None)
    call = FakeCall(**{"api.anthropic.com": error, "api.groq.com": "Резерв"})
    result = await complete(MESSAGES, [CLAUDE, FALLBACK], clock() + 15, 350, call=call, clock=clock)
    assert result == ("Резерв", "api.groq.com")
    errors = [text for level, text in log_records if level == "ERROR"]
    assert any("api.anthropic.com" in text and "ключ" in text for text in errors)
