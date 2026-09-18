from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers import commands
from services.context import ChatContextStore


@pytest.fixture
def store(monkeypatch, clock):
    fresh = ChatContextStore(ttl_seconds=900, max_chars=600, clock=clock)
    monkeypatch.setattr(commands, "store", fresh)
    return fresh


def command_message():
    message = MagicMock()
    message.chat.id = -100
    message.is_topic_message = None
    message.message_thread_id = None
    message.reply = AsyncMock()
    return message


async def test_reset_clears_context(store):
    ctx = store.get((-100, 0))
    store.add_line(ctx, "Коля: привет")
    message = command_message()
    await commands.reset_context(message)
    assert store.status((-100, 0)) is None
    message.reply.assert_awaited_once_with("Контекст разговора очищен.")


async def test_status_empty(store):
    message = command_message()
    await commands.context_status(message)
    message.reply.assert_awaited_once_with("Контекст разговора пуст.")


async def test_status_shows_numbers_not_content(store, clock):
    ctx = store.get((-100, 0))
    store.add_line(ctx, "Коля: секретный план")
    ctx.last_provider = "api.cerebras.ai"
    clock.advance(61)
    message = command_message()
    await commands.context_status(message)
    text = message.reply.await_args.args[0]
    assert "секретный" not in text
    assert "api.cerebras.ai" in text
    assert "14 мин" in text
