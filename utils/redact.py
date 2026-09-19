"""Вычищение токена бота из текста, который уходит в лог или в чат."""
from config.config import config

PLACEHOLDER = "<BOT_TOKEN>"


def redact_token(text: str) -> str:
    """Заменить токен бота в тексте на заглушку.

    Отдельно заменяется секретная часть после двоеточия: в URL двоеточие
    может оказаться закодированным как %3A, и тогда полный токен не найдётся.
    """
    token = config.BOT_TOKEN
    if not token or not text:
        return text
    text = text.replace(token, PLACEHOLDER)
    _, _, secret = token.partition(":")
    if secret:
        text = text.replace(secret, PLACEHOLDER)
    return text


def redact_log_record(record: dict) -> None:
    """Патчер loguru: вычищает токен из каждой записи до того, как она попадёт в любой приёмник."""
    record["message"] = redact_token(record["message"])
