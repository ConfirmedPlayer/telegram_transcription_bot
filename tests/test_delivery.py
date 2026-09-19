from unittest.mock import AsyncMock, MagicMock

import pytest

from services.delivery import deliver, titled


def fake_message(log):
    """Мок сообщения, который записывает порядок отправок."""
    message = MagicMock()
    message.chat.id = -100
    message.bot.send_chat_action = AsyncMock()
    message.reply = AsyncMock(side_effect=lambda text, **kw: log.append(("reply", text)))
    message.answer = AsyncMock(side_effect=lambda text, **kw: log.append(("answer", text)))
    return message


def fake_placeholder(log):
    """Мок заглушки «Обрабатываю видео...», который записывает правки и удаление."""
    placeholder = MagicMock()
    placeholder.edit_text = AsyncMock(side_effect=lambda text, **kw: log.append(("edit", text)))
    placeholder.delete = AsyncMock(side_effect=lambda **kw: log.append(("delete",)))
    return placeholder


def summarize_with(result):
    async def summarize(message, transcript):
        return result
    return summarize


def test_titled_escapes_body_but_not_title():
    assert titled("Заголовок:", "AT&T <b>") == "<b>Заголовок:</b>\n\nAT&amp;T &lt;b&gt;"


@pytest.mark.parametrize("kind, title", [
    ("voice", "Краткое содержание этого голосового сообщения:"),
    ("audio", "Краткое содержание этого аудиофайла:"),
    ("video", "Краткое содержание этого видео:"),
])
async def test_only_summary_is_sent_as_reply(kind, title):
    log = []
    await deliver(fake_message(log), "текст расшифровки", kind, summarize=summarize_with("Суть"))
    assert log == [("reply", f"<b>{title}</b>\n\nСуть")]


async def test_without_summary_nothing_is_sent():
    log = []
    await deliver(fake_message(log), "короткий текст", "audio", summarize=summarize_with(None))
    assert log == []


async def test_empty_transcript_sends_nothing():
    log = []
    await deliver(fake_message(log), "   ", "voice", summarize=summarize_with(None))
    assert log == []


async def test_summary_is_escaped():
    log = []
    await deliver(fake_message(log), "AT&T <script>", "voice", summarize=summarize_with("A & B"))
    assert log == [("reply", "<b>Краткое содержание этого голосового сообщения:</b>\n\nA &amp; B")]


async def test_video_note_placeholder_becomes_summary():
    log = []
    await deliver(fake_message(log), "текст", "video_note",
                  placeholder=fake_placeholder(log), summarize=summarize_with("Суть"))
    assert log == [("edit", "<b>Краткое содержание этого видеосообщения:</b>\n\nСуть")]


async def test_video_note_placeholder_is_deleted_without_summary():
    log = []
    await deliver(fake_message(log), "текст", "video_note",
                  placeholder=fake_placeholder(log), summarize=summarize_with(None))
    assert log == [("delete",)]
