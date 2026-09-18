"""Память разговора: скользящий контекст чата с TTL и локом на чат."""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from aiogram.types import Message

from config.config import config
from utils.text import truncate_words

ContextKey = Tuple[int, int]

MAX_PENDING_ITEMS = 3
MAX_PENDING_CHARS = 2000
SWEEP_THRESHOLD = 500


def context_key(message: Message) -> ContextKey:
    """Чат + тема форума. Вне форумных тем — 0."""
    thread = message.message_thread_id if message.is_topic_message else 0
    return (message.chat.id, thread or 0)


@dataclass
class ChatContext:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    lines: List[str] = field(default_factory=list)
    pending: List[str] = field(default_factory=list)
    updated_at: float = 0.0
    last_provider: Optional[str] = None

    def text(self) -> str:
        return "\n".join(self.lines)


@dataclass(frozen=True)
class ContextStatus:
    chars: int
    pending: int
    seconds_left: float
    last_provider: Optional[str]


class ChatContextStore:
    def __init__(
        self,
        ttl_seconds: float,
        max_chars: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_chars = max_chars
        self._clock = clock
        self._records: Dict[ContextKey, ChatContext] = {}

    def get(self, key: ContextKey) -> ChatContext:
        """Запись чата. Протухшая очищается на месте, лок при этом сохраняется."""
        if len(self._records) > SWEEP_THRESHOLD:
            self._sweep()
        ctx = self._records.get(key)
        if ctx is None:
            ctx = ChatContext(updated_at=self._clock())
            self._records[key] = ctx
        elif self._expired(ctx):
            ctx.lines.clear()
            ctx.pending.clear()
            ctx.last_provider = None
        return ctx

    def touch(self, ctx: ChatContext) -> None:
        ctx.updated_at = self._clock()

    def add_line(self, ctx: ChatContext, line: str) -> None:
        """Дописать строку; самые старые строки вытесняются целиком."""
        ctx.lines.append(line)
        while len(ctx.lines) > 1 and len(ctx.text()) > self._max_chars:
            ctx.lines.pop(0)
        if len(ctx.text()) > self._max_chars:
            ctx.lines[0] = truncate_words(ctx.lines[0], self._max_chars)

    def take_pending(self, ctx: ChatContext) -> List[str]:
        """Забрать всё из pending, оставив его пустым."""
        items = list(ctx.pending)
        ctx.pending.clear()
        return items

    def push_pending(self, ctx: ChatContext, item: str) -> None:
        """Дописать в конец pending."""
        ctx.pending.append(item)
        self._cap_pending(ctx)

    def return_pending(self, ctx: ChatContext, items: List[str]) -> None:
        """Вернуть забранное в начало pending: оно старше всего, что пришло после."""
        ctx.pending[:0] = items
        self._cap_pending(ctx)

    def reset(self, key: ContextKey) -> None:
        self._records.pop(key, None)

    def status(self, key: ContextKey) -> Optional[ContextStatus]:
        ctx = self._records.get(key)
        if ctx is None or self._expired(ctx) or not (ctx.lines or ctx.pending):
            return None
        return ContextStatus(
            chars=len(ctx.text()),
            pending=len(ctx.pending),
            seconds_left=self._ttl - (self._clock() - ctx.updated_at),
            last_provider=ctx.last_provider,
        )

    def clear(self) -> None:
        self._records.clear()

    def __len__(self) -> int:
        return len(self._records)

    def _expired(self, ctx: ChatContext) -> bool:
        return self._clock() - ctx.updated_at > self._ttl

    def _cap_pending(self, ctx: ChatContext) -> None:
        while len(ctx.pending) > MAX_PENDING_ITEMS:
            ctx.pending.pop(0)
        while len(ctx.pending) > 1 and len("\n".join(ctx.pending)) > MAX_PENDING_CHARS:
            ctx.pending.pop(0)
        if ctx.pending and len(ctx.pending[0]) > MAX_PENDING_CHARS:
            ctx.pending[0] = truncate_words(ctx.pending[0], MAX_PENDING_CHARS)

    def _sweep(self) -> None:
        stale = [
            key for key, ctx in self._records.items()
            if self._expired(ctx) and not ctx.lock.locked()
        ]
        for key in stale:
            del self._records[key]


store = ChatContextStore(
    ttl_seconds=config.SUMMARY_CONTEXT_TTL_MINUTES * 60,
    max_chars=config.SUMMARY_CONTEXT_MAX_CHARS,
)
