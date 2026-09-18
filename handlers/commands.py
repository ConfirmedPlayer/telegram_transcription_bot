"""Команды управления памятью разговора."""
import math

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from services.context import context_key, store

router = Router()


@router.message(Command("reset"))
async def reset_context(message: Message):
    store.reset(context_key(message))
    await message.reply("Контекст разговора очищен.")


@router.message(Command("status"))
async def context_status(message: Message):
    status = store.status(context_key(message))
    if status is None:
        await message.reply("Контекст разговора пуст.")
        return
    minutes = max(1, math.ceil(status.seconds_left / 60))
    provider = status.last_provider or "ещё не отвечал"
    await message.reply(
        f"Контекст: {status.chars} симв., ждут сводки: {status.pending}.\n"
        f"Сбросится примерно через {minutes} мин. без новых сообщений.\n"
        f"Последний провайдер: {provider}."
    )
