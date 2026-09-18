import asyncio

import httpx2
import openai

from services.llm import Provider, complete, strip_think

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
