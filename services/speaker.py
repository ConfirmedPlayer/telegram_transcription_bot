"""Кто сказал реплику: подпись для контекста и промпта."""
from typing import Optional

from aiogram.types import (
    Message,
    MessageOriginChannel,
    MessageOriginChat,
    MessageOriginHiddenUser,
    MessageOriginUser,
)

from utils.text import one_line

MAX_NAME_CHARS = 32


def _clean(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    return one_line(name)[:MAX_NAME_CHARS] or None


def _origin_name(origin) -> Optional[str]:
    if isinstance(origin, MessageOriginUser):
        return _clean(origin.sender_user.full_name)
    if isinstance(origin, MessageOriginHiddenUser):
        return _clean(origin.sender_user_name)
    if isinstance(origin, MessageOriginChat):
        return _clean(origin.author_signature or origin.sender_chat.title)
    if isinstance(origin, MessageOriginChannel):
        return _clean(origin.author_signature or origin.chat.title)
    return None


def resolve_speaker(message: Message) -> Optional[str]:
    """Подпись автора реплики или None, если подписать нечем."""
    if message.forward_origin is not None:
        source = _origin_name(message.forward_origin)
        return f"переслано от {source}" if source else "переслано"
    if message.sender_chat is not None:
        return _clean(message.author_signature or message.sender_chat.title)
    if message.from_user is None:
        return None
    return _clean(message.from_user.full_name)


def attribute(speaker: Optional[str], text: str) -> str:
    """Строка вида «Имя: текст» или просто текст, если автор неизвестен."""
    return f"{speaker}: {text}" if speaker else text
