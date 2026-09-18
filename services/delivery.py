"""Отправка в чат: сначала сводка, потом расшифровка; заголовки, reply, экранирование."""
import html
from typing import Awaitable, Callable, Optional

from aiogram.types import Message

from services import summary
from utils.formatting import split_long_message

# Запас под заголовок и рост текста при экранировании до лимита Telegram в 4096 символов
TRANSCRIPT_CHUNK = 3500
EMPTY_TRANSCRIPT = "— речь не распознана —"

TITLES = {
    "voice": ("Краткое содержание этого голосового сообщения:", "Расшифровка голосового сообщения:"),
    "audio": ("Краткое содержание этого аудиофайла:", "Расшифровка аудиофайла:"),
    "video": ("Краткое содержание этого видео:", "Расшифровка видео:"),
    "video_note": ("Краткое содержание этого видеосообщения:", "Расшифровка видеосообщения:"),
}

SummarizeFn = Callable[[Message, str], Awaitable[Optional[str]]]


def titled(title: str, body: str) -> str:
    """Заголовок жирным, пустая строка, экранированный текст."""
    return f"<b>{title}</b>\n\n{html.escape(body)}"


async def deliver(
    message: Message,
    transcript: str,
    kind: str,
    placeholder: Optional[Message] = None,
    summarize: Optional[SummarizeFn] = None,
) -> None:
    """Отправить сводку (если есть) и расшифровку ответом на исходное сообщение.

    placeholder — уже отправленное ботом сообщение-заглушка: первое сообщение
    не отправляется заново, а записывается поверх неё.
    """
    summary_title, transcript_title = TITLES[kind]
    await message.bot.send_chat_action(message.chat.id, "typing")
    summary_text = await (summarize or summary.build_summary)(message, transcript)

    if summary_text:
        await _send_first(message, placeholder, titled(summary_title, summary_text))
        placeholder = None

    parts = split_long_message(transcript, limit=TRANSCRIPT_CHUNK) if transcript.strip() else [EMPTY_TRANSCRIPT]
    await _send_first(message, placeholder, titled(transcript_title, parts[0]))
    for part in parts[1:]:
        await message.answer(html.escape(part))


async def _send_first(message: Message, placeholder: Optional[Message], text: str) -> None:
    if placeholder is not None:
        await placeholder.edit_text(text)
    else:
        await message.reply(text)
