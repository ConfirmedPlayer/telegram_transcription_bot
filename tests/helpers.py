import datetime

from aiogram.types import Chat, Message, User


def make_message(chat_id: int = -100, user_name: str = "Коля", **fields) -> Message:
    """Настоящий aiogram Message без привязки к боту — для чистых функций."""
    fields.setdefault("from_user", User(id=1, is_bot=False, first_name=user_name))
    return Message(
        message_id=fields.pop("message_id", 1),
        date=datetime.datetime(2026, 9, 18, 12, 0),
        chat=Chat(id=chat_id, type="supergroup", title="Группа"),
        **fields,
    )


class FakeClock:
    """Управляемые монотонные часы."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds
