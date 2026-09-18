import asyncio

from services.context import ChatContextStore, context_key
from services.llm import Provider
from services.summary import Summarizer, SummarySettings
from tests.helpers import make_message

TEMPLATE = "КОНТЕКСТ:\n{context}\nРЕПЛИКА:\n{utterance}"
PROVIDERS = [Provider("https://api.cerebras.ai/v1", "key", "qwen-3.8-27b")]
LONG = " ".join(["слово"] * 120)


def settings(**overrides) -> SummarySettings:
    values = dict(min_words=100, context_min_words=1, total_timeout=15,
                  max_output_tokens=350, max_input_chars=12000)
    values.update(overrides)
    return SummarySettings(**values)


class FakeComplete:
    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    async def __call__(self, messages, providers, deadline, max_tokens, **kwargs):
        self.prompts.append(messages[0]["content"])
        answer = self.answers.pop(0)
        if callable(answer):
            return await answer()
        return answer


def make_summarizer(store, complete, providers=PROVIDERS, **overrides):
    return Summarizer(store, providers, settings(**overrides), TEMPLATE, complete=complete)


async def test_disabled_without_keys(clock):
    store = ChatContextStore(900, 600, clock=clock)
    fake = FakeComplete([])
    no_keys = [Provider("https://api.cerebras.ai/v1", "", "m")]
    assert await make_summarizer(store, fake, providers=no_keys).build(make_message(), LONG) is None
    assert len(store) == 0


async def test_short_reply_goes_to_context_without_model_call(clock):
    store = ChatContextStore(900, 600, clock=clock)
    fake = FakeComplete([])
    msg = make_message(user_name="Маша")
    assert await make_summarizer(store, fake).build(msg, "да, во вторник") is None
    assert store.get(context_key(msg)).lines == ["Маша: да, во вторник"]
    assert fake.prompts == []


async def test_long_reply_summarized_with_context_and_speaker(clock):
    store = ChatContextStore(900, 600, clock=clock)
    msg = make_message(user_name="Коля")
    store.add_line(store.get(context_key(msg)), "Маша: обсуждаем торт")
    fake = FakeComplete([("Коля за шоколадный торт", "api.cerebras.ai")])
    summary = await make_summarizer(store, fake).build(msg, LONG)
    assert summary == "Коля за шоколадный торт"
    assert "Маша: обсуждаем торт" in fake.prompts[0]
    assert "Коля: слово" in fake.prompts[0]
    ctx = store.get(context_key(msg))
    assert ctx.lines[-1] == "Коля: Коля за шоколадный торт"
    assert ctx.last_provider == "api.cerebras.ai"


async def test_empty_context_placeholder(clock):
    store = ChatContextStore(900, 600, clock=clock)
    fake = FakeComplete([("Сводка", "api.cerebras.ai")])
    await make_summarizer(store, fake).build(make_message(), LONG)
    assert "(разговор только начался)" in fake.prompts[0]


async def test_failure_keeps_utterance_in_pending_and_next_call_uses_it(clock):
    store = ChatContextStore(900, 600, clock=clock)
    fake = FakeComplete([None, ("Вторая сводка", "api.groq.com")])
    summarizer = make_summarizer(store, fake)
    first = make_message(user_name="Коля")
    assert await summarizer.build(first, LONG) is None
    ctx = store.get(context_key(first))
    assert len(ctx.pending) == 1 and ctx.pending[0].startswith("Коля: ")

    await summarizer.build(make_message(user_name="Маша"), LONG)
    assert "Коля: слово" in fake.prompts[1]  # пропущенная реплика догнала контекст
    assert ctx.pending == []
    assert ctx.lines[0].startswith("Коля: ")
    assert ctx.lines[-1] == "Маша: Вторая сводка"


async def test_concurrent_messages_do_not_overwrite_each_other(clock):
    store = ChatContextStore(900, 600, clock=clock)
    gate = asyncio.Event()

    async def first_answer():
        await gate.wait()
        return ("Сводка Коли", "api.cerebras.ai")

    fake = FakeComplete([first_answer, ("Сводка Маши", "api.cerebras.ai")])
    summarizer = make_summarizer(store, fake)
    kolya = asyncio.create_task(summarizer.build(make_message(user_name="Коля"), LONG))
    await asyncio.sleep(0)
    masha = asyncio.create_task(summarizer.build(make_message(user_name="Маша"), LONG))
    await asyncio.sleep(0.01)
    gate.set()
    await asyncio.gather(kolya, masha)

    ctx = store.get((-100, 0))
    assert ctx.lines == ["Коля: Сводка Коли", "Маша: Сводка Маши"]
    assert "Коля: Сводка Коли" in fake.prompts[1]  # вторая сводка видела первую


async def test_lock_wait_is_bounded_and_utterance_is_kept():
    store = ChatContextStore(900, 600)
    gate = asyncio.Event()

    async def stuck():
        await gate.wait()
        return ("Сводка Коли", "api.cerebras.ai")

    fake = FakeComplete([stuck])
    summarizer = make_summarizer(store, fake, total_timeout=0.1)
    kolya = asyncio.create_task(summarizer.build(make_message(user_name="Коля"), LONG))
    await asyncio.sleep(0)
    assert await summarizer.build(make_message(user_name="Маша"), LONG) is None
    ctx = store.get((-100, 0))
    assert ctx.pending and ctx.pending[-1].startswith("Маша: ")
    gate.set()
    await kolya
    assert not ctx.lock.locked()


async def test_long_transcript_is_truncated_for_model(clock):
    store = ChatContextStore(900, 600, clock=clock)
    fake = FakeComplete([("Сводка", "api.cerebras.ai")])
    await make_summarizer(store, fake, max_input_chars=300).build(make_message(), LONG * 10)
    utterance = fake.prompts[0].split("РЕПЛИКА:\n", 1)[1]
    assert len(utterance) <= len("Коля: ") + 300
