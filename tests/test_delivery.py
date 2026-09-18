from unittest.mock import AsyncMock, MagicMock

from services.delivery import EMPTY_TRANSCRIPT, TRANSCRIPT_CHUNK, deliver, titled


def fake_message(log):
    """Мок сообщения, который записывает порядок отправок."""
    message = MagicMock()
    message.chat.id = -100
    message.bot.send_chat_action = AsyncMock()
    message.reply = AsyncMock(side_effect=lambda text, **kw: log.append(("reply", text)))
    message.answer = AsyncMock(side_effect=lambda text, **kw: log.append(("answer", text)))
    return message


def summarize_with(result):
    async def summarize(message, transcript):
        return result
    return summarize


def test_titled_escapes_body_but_not_title():
    assert titled("Заголовок:", "AT&T <b>") == "<b>Заголовок:</b>\n\nAT&amp;T &lt;b&gt;"


async def test_summary_is_sent_before_transcript_both_as_replies():
    log = []
    await deliver(fake_message(log), "текст расшифровки", "voice", summarize=summarize_with("Суть"))
    assert log == [
        ("reply", "<b>Краткое содержание этого голосового сообщения:</b>\n\nСуть"),
        ("reply", "<b>Расшифровка голосового сообщения:</b>\n\nтекст расшифровки"),
    ]


async def test_without_summary_only_transcript():
    log = []
    await deliver(fake_message(log), "короткий текст", "audio", summarize=summarize_with(None))
    assert log == [("reply", "<b>Расшифровка аудиофайла:</b>\n\nкороткий текст")]


async def test_long_transcript_header_only_on_first_part():
    log = []
    transcript = ("слово " * (TRANSCRIPT_CHUNK // 3)).strip()
    await deliver(fake_message(log), transcript, "video", summarize=summarize_with(None))
    assert len(log) >= 2
    assert log[0][0] == "reply" and log[0][1].startswith("<b>Расшифровка видео:</b>")
    assert all(kind == "answer" and "<b>" not in text for kind, text in log[1:])


async def test_transcript_is_escaped():
    log = []
    await deliver(fake_message(log), "AT&T <script>", "voice", summarize=summarize_with("A & B"))
    assert "A &amp; B" in log[0][1]
    assert "AT&amp;T &lt;script&gt;" in log[1][1]


async def test_empty_transcript_shows_placeholder_text():
    log = []
    await deliver(fake_message(log), "   ", "voice", summarize=summarize_with(None))
    assert log == [("reply", f"<b>Расшифровка голосового сообщения:</b>\n\n{EMPTY_TRANSCRIPT}")]


async def test_video_note_placeholder_becomes_summary_then_transcript_below():
    log = []
    message = fake_message(log)
    placeholder = MagicMock()
    placeholder.edit_text = AsyncMock(side_effect=lambda text, **kw: log.append(("edit", text)))
    await deliver(message, "текст", "video_note", placeholder=placeholder, summarize=summarize_with("Суть"))
    assert log == [
        ("edit", "<b>Краткое содержание этого видеосообщения:</b>\n\nСуть"),
        ("reply", "<b>Расшифровка видеосообщения:</b>\n\nтекст"),
    ]


async def test_video_note_placeholder_becomes_transcript_without_summary():
    log = []
    message = fake_message(log)
    placeholder = MagicMock()
    placeholder.edit_text = AsyncMock(side_effect=lambda text, **kw: log.append(("edit", text)))
    await deliver(message, "текст", "video_note", placeholder=placeholder, summarize=summarize_with(None))
    assert log == [("edit", "<b>Расшифровка видеосообщения:</b>\n\nтекст")]
