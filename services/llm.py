"""Запрос сводки: два OpenAI-совместимых провайдера, общий дедлайн, ровно одна попытка на каждого."""
import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import openai
from loguru import logger

from config.config import config

MIN_ATTEMPT_SECONDS = 2.0
CONNECT_TIMEOUT = 3.0

Messages = List[Dict[str, str]]

_THINK_BLOCK = re.compile(r"^\s*<think>.*?</think>", re.S | re.I)
_AUTH_ERRORS = (openai.AuthenticationError, openai.PermissionDeniedError, openai.NotFoundError)


@dataclass(frozen=True)
class Provider:
    base_url: str
    api_key: str
    model: str
    extra: Dict[str, object] = field(default_factory=dict, hash=False, compare=False)

    @property
    def name(self) -> str:
        return urlparse(self.base_url).hostname or self.base_url


def strip_think(text: Optional[str]) -> str:
    """Убрать ведущий блок <think>…</think>. Незакрытый блок — это пустой ответ."""
    text = _THINK_BLOCK.sub("", text or "", count=1).strip()
    if text.lower().startswith("<think>"):
        return ""
    return text


_clients: Dict[Tuple[str, str], openai.AsyncOpenAI] = {}


def _client(provider: Provider) -> openai.AsyncOpenAI:
    key = (provider.base_url, provider.api_key)
    client = _clients.get(key)
    if client is None:
        # max_retries=0: иначе SDK повторяет запрос сам и спит по retry-after, съедая дедлайн
        client = openai.AsyncOpenAI(base_url=provider.base_url, api_key=provider.api_key, max_retries=0)
        _clients[key] = client
    return client


async def call_provider(provider: Provider, messages: Messages, max_tokens: int, timeout: float) -> str:
    """Один запрос к провайдеру."""
    response = await _client(provider).chat.completions.create(
        model=provider.model,
        messages=messages,
        max_completion_tokens=max_tokens,
        timeout=openai.Timeout(timeout, connect=CONNECT_TIMEOUT, write=CONNECT_TIMEOUT, pool=CONNECT_TIMEOUT),
        extra_body=provider.extra or None,
    )
    return response.choices[0].message.content or ""


CallFn = Callable[[Provider, Messages, int, float], Awaitable[str]]


async def complete(
    messages: Messages,
    providers: List[Provider],
    deadline: float,
    max_tokens: int,
    *,
    call: CallFn = call_provider,
    clock: Callable[[], float] = time.monotonic,
    min_attempt: float = MIN_ATTEMPT_SECONDS,
) -> Optional[Tuple[str, str]]:
    """Вернуть (текст, имя провайдера) или None, если не ответил никто."""
    for provider in providers:
        if not provider.api_key:
            continue
        remaining = deadline - clock()
        if remaining < min_attempt:
            logger.warning(f"Сводка: не осталось времени на попытку {provider.name}")
            break
        try:
            raw = await asyncio.wait_for(call(provider, messages, max_tokens, remaining), timeout=remaining)
        except asyncio.TimeoutError:
            logger.warning(f"Сводка: {provider.name} не ответил за {remaining:.1f} с")
            continue
        except _AUTH_ERRORS as error:
            logger.error(f"Сводка: {provider.name} отклонил запрос — проверьте ключ или имя модели: {error}")
            continue
        except Exception as error:
            logger.warning(f"Сводка: ошибка {provider.name}: {error}")
            continue
        text = strip_think(raw)
        if text:
            return text, provider.name
        logger.warning(f"Сводка: {provider.name} вернул пустой ответ")
    return None


def _extra(raw: str) -> Dict[str, object]:
    if not raw.strip():
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("LLM_*_EXTRA должен быть JSON-объектом")
    return value


def configured_providers() -> List[Provider]:
    return [
        Provider(config.LLM_PRIMARY_BASE_URL, config.LLM_PRIMARY_API_KEY,
                 config.LLM_PRIMARY_MODEL, _extra(config.LLM_PRIMARY_EXTRA)),
        Provider(config.LLM_FALLBACK_BASE_URL, config.LLM_FALLBACK_API_KEY,
                 config.LLM_FALLBACK_MODEL, _extra(config.LLM_FALLBACK_EXTRA)),
    ]
