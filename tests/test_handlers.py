from unittest.mock import AsyncMock, MagicMock

import pytest

from handlers import audio, video, voice
from models.transcription import TranscriptionResult


def media_message(kind):
    message = MagicMock()
    message.bot.send_chat_action = AsyncMock()
    message.bot.get_file = AsyncMock(return_value=MagicMock(file_path="voice/file.oga"))
    message.reply = AsyncMock(return_value=MagicMock(edit_text=AsyncMock()))
    message.answer = AsyncMock()
    getattr(message, kind).file_id = "file-id"
    return message


@pytest.mark.parametrize("module, handler, kind", [
    (voice, "handle_voice", "voice"),
    (audio, "handle_audio", "audio"),
    (video, "handle_video", "video"),
])
async def test_handler_passes_transcript_and_kind_to_deliver(monkeypatch, module, handler, kind):
    deliver = AsyncMock()
    monkeypatch.setattr(module, "deliver", deliver)
    monkeypatch.setattr(module.deepgram_service, "transcribe_audio",
                        AsyncMock(return_value=TranscriptionResult(text="расшифровка", confidence=1.0, words=[])))
    message = media_message(kind)
    await getattr(module, handler)(message)
    deliver.assert_awaited_once_with(message, "расшифровка", kind)


async def test_video_note_passes_placeholder(monkeypatch):
    deliver = AsyncMock()
    monkeypatch.setattr(video, "deliver", deliver)
    monkeypatch.setattr(video.deepgram_service, "transcribe_audio",
                        AsyncMock(return_value=TranscriptionResult(text="расшифровка", confidence=1.0, words=[])))
    message = media_message("video_note")
    await video.handle_video_note(message)
    placeholder = message.reply.return_value
    deliver.assert_awaited_once_with(message, "расшифровка", "video_note", placeholder=placeholder)
