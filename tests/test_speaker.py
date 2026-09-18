import datetime

from aiogram.types import (
    Chat,
    MessageOriginChannel,
    MessageOriginHiddenUser,
    MessageOriginUser,
    User,
)

from services.speaker import attribute, resolve_speaker
from tests.helpers import make_message

DATE = datetime.datetime(2026, 9, 18)


def test_regular_user_full_name():
    user = User(id=1, is_bot=False, first_name="Коля", last_name="Петров")
    assert resolve_speaker(make_message(from_user=user)) == "Коля Петров"


def test_name_is_single_line_and_capped_at_32_chars():
    user = User(id=1, is_bot=False, first_name="Очень\nдлинное имя " + "я" * 40)
    name = resolve_speaker(make_message(from_user=user))
    assert "\n" not in name
    assert len(name) == 32


def test_anonymous_admin_uses_signature_or_chat_title():
    group = Chat(id=-100, type="supergroup", title="Группа")
    assert resolve_speaker(make_message(sender_chat=group, author_signature="Админ")) == "Админ"
    assert resolve_speaker(make_message(sender_chat=group)) == "Группа"


def test_no_sender_means_no_attribution():
    assert resolve_speaker(make_message(from_user=None)) is None


def test_forward_from_user():
    origin = MessageOriginUser(date=DATE, sender_user=User(id=2, is_bot=False, first_name="Антон"))
    assert resolve_speaker(make_message(forward_origin=origin)) == "переслано от Антон"


def test_forward_from_hidden_user():
    origin = MessageOriginHiddenUser(date=DATE, sender_user_name="Скрытый")
    assert resolve_speaker(make_message(forward_origin=origin)) == "переслано от Скрытый"


def test_forward_from_channel_prefers_signature():
    channel = Chat(id=-200, type="channel", title="Новости")
    signed = MessageOriginChannel(date=DATE, chat=channel, message_id=5, author_signature="Редактор")
    unsigned = MessageOriginChannel(date=DATE, chat=channel, message_id=5)
    assert resolve_speaker(make_message(forward_origin=signed)) == "переслано от Редактор"
    assert resolve_speaker(make_message(forward_origin=unsigned)) == "переслано от Новости"


def test_attribute_formats_line():
    assert attribute("Коля", "привет") == "Коля: привет"
    assert attribute(None, "привет") == "привет"
