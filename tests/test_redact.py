import pytest
from loguru import logger

from config.config import config
from utils.redact import PLACEHOLDER, redact_log_record, redact_token

SECRET = "AAHsecretPartOfToken_42"
TOKEN = f"123456:{SECRET}"


@pytest.fixture(autouse=True)
def token(monkeypatch):
    monkeypatch.setattr(config, "BOT_TOKEN", TOKEN)


def test_full_token_is_replaced():
    text = f"https://api.telegram.org/file/bot{TOKEN}/voice.oga"
    assert redact_token(text) == f"https://api.telegram.org/file/bot{PLACEHOLDER}/voice.oga"


def test_secret_part_is_replaced_even_with_encoded_colon():
    text = f"https://api.telegram.org/file/bot123456%3A{SECRET}/voice.oga"
    assert SECRET not in redact_token(text)


def test_text_without_token_is_unchanged():
    assert redact_token("обычная ошибка") == "обычная ошибка"


def test_without_configured_token_text_is_unchanged(monkeypatch):
    monkeypatch.setattr(config, "BOT_TOKEN", None)
    assert redact_token(f"bot{TOKEN}") == f"bot{TOKEN}"


def test_log_patcher_redacts_message(log_records):
    logger.configure(patcher=redact_log_record)
    try:
        logger.error(f"упало на https://api.telegram.org/file/bot{TOKEN}/v.oga")
    finally:
        # configure(patcher=None) патчер не сбрасывает — нужен явный no-op
        logger.configure(patcher=lambda record: None)
    assert log_records
    assert all(SECRET not in text for _, text in log_records)
