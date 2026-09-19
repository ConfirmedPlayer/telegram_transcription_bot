"""Отправка в чат только сводки: заголовок, reply, экранирование. Расшифровка в чат не уходит."""
import html
from typing import Awaitable, Callable, Optional

from aiogram.types import Message

from services import summary

TITLES = {
    "voice": "Краткое содержание этого голосового сообщения:",
    "audio": "Краткое содержание этого аудиофайла:",
    "video": "Краткое содержание этого видео:",
    "video_note": "Краткое содержание этого видеосообщения:",
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
    """Отправить сводку ответом на исходное сообщение; расшифровка нужна только для неё.

    Сводки нет (реплика короче порога, речь не распознана, провайдеры не ответили
    или не настроены) — бот в чат ничего не пишет.

    placeholder — уже отправленное ботом сообщение-заглушка: сводка записывается
    поверх неё, а без сводки заглушка удаляется.
    """
    await message.bot.send_chat_action(message.chat.id, "typing")
    summary_text = await (summarize or summary.build_summary)(message, transcript)

    if summary_text:
        text = titled(TITLES[kind], summary_text)
        if placeholder is not None:
            await placeholder.edit_text(text)
        else:
            await message.reply(text)
    elif placeholder is not None:
        await placeholder.delete()
