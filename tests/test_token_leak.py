import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from config.config import config
from handlers import audio, video, voice
from models.transcription import TranscriptionResult

SECRET = "AAHsecretPartOfToken_42"
TOKEN = f"123456:{SECRET}"
REPO = Path(__file__).resolve().parent.parent

HANDLERS = [
    (voice, "handle_voice", "voice"),
    (audio, "handle_audio", "audio"),
    (video, "handle_video", "video"),
    (video, "handle_video_note", "video_note"),
]


@pytest.fixture(autouse=True)
def token(monkeypatch):
    monkeypatch.setattr(config, "BOT_TOKEN", TOKEN)


def media_message(kind):
    message = MagicMock()
    message.bot.send_chat_action = AsyncMock()
    message.bot.get_file = AsyncMock(return_value=MagicMock(file_path="voice/file_1.oga"))
    message.reply = AsyncMock(return_value=MagicMock(edit_text=AsyncMock()))
    message.answer = AsyncMock()
    getattr(message, kind).file_id = "file-id"
    return message


def sent_texts(message):
    """Всё, что бот отправил в чат или записал в сообщение-заглушку."""
    calls = message.answer.await_args_list + message.reply.return_value.edit_text.await_args_list
    return [call.args[0] for call in calls if call.args]


@pytest.mark.parametrize("module, handler, kind", HANDLERS)
async def test_handling_does_not_log_token(monkeypatch, log_records, module, handler, kind):
    monkeypatch.setattr(module, "deliver", AsyncMock())
    monkeypatch.setattr(module.deepgram_service, "transcribe_audio",
                        AsyncMock(return_value=TranscriptionResult(text="т", confidence=1.0, words=[])))
    await getattr(module, handler)(media_message(kind))
    assert all(SECRET not in text for _, text in log_records)


@pytest.mark.parametrize("module, handler, kind", HANDLERS)
async def test_error_sent_to_chat_does_not_contain_token(monkeypatch, module, handler, kind):
    url = f"https://api.telegram.org/file/bot{TOKEN}/voice/file_1.oga"
    monkeypatch.setattr(module.deepgram_service, "transcribe_audio",
                        AsyncMock(side_effect=aiohttp.InvalidUrlClientError(url)))
    message = media_message(kind)
    await getattr(module, handler)(message)
    texts = sent_texts(message)
    assert texts, "бот должен сообщить об ошибке"
    assert all(SECRET not in text for text in texts)


async def test_video_note_truncation_cannot_expose_part_of_token(monkeypatch):
    # Обрезка [:200] приходится на середину токена: видно ровно 6 первых символов секрета
    prefix = "x" * (200 - len("https://api.telegram.org/file/bot123456:") - 6)
    url = f"https://api.telegram.org/file/bot{TOKEN}/v.oga"
    monkeypatch.setattr(video.deepgram_service, "transcribe_audio",
                        AsyncMock(side_effect=RuntimeError(prefix + url)))
    message = media_message("video_note")
    await video.handle_video_note(message)
    (text,) = sent_texts(message)
    assert SECRET[:6] not in text


def test_bot_logs_are_redacted_end_to_end(tmp_path):
    """Настоящий import main в отдельном процессе: stderr и logs/bot.log без токена."""
    code = (
        "import main\n"
        "from loguru import logger\n"
        f"logger.error('упало на https://api.telegram.org/file/bot{TOKEN}/v.oga')\n"
    )
    env = {**os.environ, "BOT_TOKEN": TOKEN, "PYTHONPATH": str(REPO)}
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    log_file = tmp_path / "logs" / "bot.log"
    assert log_file.exists()
    assert "упало на" in result.stderr  # запись действительно попала в stderr
    assert SECRET not in result.stderr
    assert SECRET not in log_file.read_text(encoding="utf-8")
