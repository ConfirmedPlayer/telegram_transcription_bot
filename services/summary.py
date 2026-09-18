"""Сводка голосового с учётом памяти разговора."""
import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, List, Optional, Tuple

from aiogram.types import Message
from loguru import logger

from config.config import config
from services import llm
from services.context import ChatContextStore, context_key, store
from services.speaker import attribute, resolve_speaker
from utils.text import one_line, truncate_words

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "summary.md"
EMPTY_CONTEXT = "(разговор только начался)"
SHORT_REPLY_CHARS = 200


@dataclass(frozen=True)
class SummarySettings:
    min_words: int
    context_min_words: int
    total_timeout: float
    max_output_tokens: int
    max_input_chars: int


CompleteFn = Callable[..., Awaitable[Optional[Tuple[str, str]]]]


class Summarizer:
    def __init__(
        self,
        store: ChatContextStore,
        providers: List[llm.Provider],
        settings: SummarySettings,
        prompt_template: str,
        complete: CompleteFn = llm.complete,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._store = store
        self._providers = providers
        self._settings = settings
        self._template = prompt_template
        self._complete = complete
        self._clock = clock

    @property
    def enabled(self) -> bool:
        return any(provider.api_key for provider in self._providers)

    async def build(self, message: Message, transcript: str) -> Optional[str]:
        """Сводка новой реплики или None. Никогда не бросает исключений наружу из-за провайдеров."""
        words = len(transcript.split())
        if not self.enabled or words == 0:
            return None

        speaker = resolve_speaker(message)
        ctx = self._store.get(context_key(message))
        self._store.touch(ctx)  # TTL продлевает приход сообщения, а не успех сводки

        if words < self._settings.min_words:
            if words >= self._settings.context_min_words:
                short = truncate_words(one_line(transcript), SHORT_REPLY_CHARS)
                self._store.add_line(ctx, attribute(speaker, short))
            return None

        deadline = self._clock() + self._settings.total_timeout
        utterance = attribute(speaker, truncate_words(one_line(transcript), self._settings.max_input_chars))

        try:
            await asyncio.wait_for(ctx.lock.acquire(), timeout=max(deadline - self._clock(), 0.0))
        except asyncio.TimeoutError:
            logger.warning("Сводка пропущена: в этом чате ещё строится предыдущая")
            self._store.push_pending(ctx, utterance)
            return None

        try:
            consumed = self._store.take_pending(ctx)
            prompt = self._render(ctx.lines + consumed, utterance)
            result = await self._complete(
                [{"role": "user", "content": prompt}],
                self._providers,
                deadline,
                self._settings.max_output_tokens,
                clock=self._clock,
            )
            if result is None:
                self._store.return_pending(ctx, consumed + [utterance])
                return None
            summary, provider = result
            for item in consumed:
                self._store.add_line(ctx, truncate_words(item, SHORT_REPLY_CHARS))
            self._store.add_line(ctx, attribute(speaker, one_line(summary)))
            ctx.last_provider = provider
            return summary
        finally:
            ctx.lock.release()

    def _render(self, context_lines: List[str], utterance: str) -> str:
        context = "\n".join(context_lines) or EMPTY_CONTEXT
        return self._template.format(context=context, utterance=utterance)


summarizer = Summarizer(
    store=store,
    providers=llm.configured_providers(),
    settings=SummarySettings(
        min_words=config.SUMMARY_MIN_WORDS,
        context_min_words=config.CONTEXT_MIN_WORDS,
        total_timeout=config.SUMMARY_TOTAL_TIMEOUT,
        max_output_tokens=config.SUMMARY_MAX_OUTPUT_TOKENS,
        max_input_chars=config.SUMMARY_MAX_INPUT_CHARS,
    ),
    prompt_template=PROMPT_PATH.read_text(encoding="utf-8"),
)


async def build_summary(message: Message, transcript: str) -> Optional[str]:
    return await summarizer.build(message, transcript)
