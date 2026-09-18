from services.context import MAX_PENDING_ITEMS, ChatContextStore, context_key
from tests.helpers import make_message


def test_key_is_chat_and_zero_outside_forum_topics():
    assert context_key(make_message(chat_id=-100)) == (-100, 0)


def test_key_includes_topic_only_for_topic_messages():
    in_topic = make_message(chat_id=-100, message_thread_id=7, is_topic_message=True)
    thread_not_topic = make_message(chat_id=-100, message_thread_id=7)
    assert context_key(in_topic) == (-100, 7)
    assert context_key(thread_not_topic) == (-100, 0)


def test_new_record_is_empty(clock):
    store = ChatContextStore(ttl_seconds=900, max_chars=600, clock=clock)
    ctx = store.get((1, 0))
    assert ctx.lines == [] and ctx.pending == []


def test_lines_evicted_oldest_first_by_whole_line(clock):
    store = ChatContextStore(ttl_seconds=900, max_chars=20, clock=clock)
    ctx = store.get((1, 0))
    store.add_line(ctx, "Коля: раз")      # 9
    store.add_line(ctx, "Маша: два")      # 9 + 1 + 9 = 19
    store.add_line(ctx, "Антон: три")     # вытесняет первую строку целиком
    assert ctx.lines == ["Маша: два", "Антон: три"]


def test_single_oversized_line_is_truncated(clock):
    store = ChatContextStore(ttl_seconds=900, max_chars=10, clock=clock)
    ctx = store.get((1, 0))
    store.add_line(ctx, "Коля: очень длинная реплика")
    assert len(ctx.text()) <= 10


def test_expired_record_is_cleared_but_keeps_its_lock(clock):
    store = ChatContextStore(ttl_seconds=900, max_chars=600, clock=clock)
    ctx = store.get((1, 0))
    lock = ctx.lock
    store.add_line(ctx, "Коля: привет")
    clock.advance(901)
    again = store.get((1, 0))
    assert again.lines == []
    assert again.lock is lock


def test_touch_extends_ttl(clock):
    store = ChatContextStore(ttl_seconds=900, max_chars=600, clock=clock)
    ctx = store.get((1, 0))
    store.add_line(ctx, "Коля: привет")
    clock.advance(800)
    store.touch(ctx)
    clock.advance(800)
    assert store.get((1, 0)).lines == ["Коля: привет"]


def test_pending_keeps_last_three(clock):
    store = ChatContextStore(ttl_seconds=900, max_chars=600, clock=clock)
    ctx = store.get((1, 0))
    for i in range(MAX_PENDING_ITEMS + 2):
        store.push_pending(ctx, f"реплика {i}")
    assert ctx.pending == ["реплика 2", "реплика 3", "реплика 4"]


def test_returned_pending_goes_before_newer_items(clock):
    store = ChatContextStore(ttl_seconds=900, max_chars=600, clock=clock)
    ctx = store.get((1, 0))
    store.push_pending(ctx, "старое")
    taken = store.take_pending(ctx)
    store.push_pending(ctx, "новое")
    store.return_pending(ctx, taken)
    assert ctx.pending == ["старое", "новое"]


def test_status_and_reset(clock):
    store = ChatContextStore(ttl_seconds=900, max_chars=600, clock=clock)
    assert store.status((1, 0)) is None
    ctx = store.get((1, 0))
    store.add_line(ctx, "Коля: привет")
    ctx.last_provider = "api.cerebras.ai"
    clock.advance(60)
    status = store.status((1, 0))
    assert status.chars == len("Коля: привет")
    assert status.seconds_left == 840
    assert status.last_provider == "api.cerebras.ai"
    store.reset((1, 0))
    assert store.status((1, 0)) is None


def test_sweep_drops_expired_unlocked_records_over_threshold(clock, monkeypatch):
    monkeypatch.setattr("services.context.SWEEP_THRESHOLD", 2)
    store = ChatContextStore(ttl_seconds=900, max_chars=600, clock=clock)
    for chat in range(3):
        store.get((chat, 0))
    clock.advance(901)
    store.get((99, 0))
    assert len(store) == 1
