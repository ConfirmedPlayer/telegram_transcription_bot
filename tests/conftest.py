import pytest
from loguru import logger

from tests.helpers import FakeClock


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def log_records():
    """Сообщения loguru, записанные за время теста: список (уровень, текст)."""
    records = []
    handler_id = logger.add(
        lambda message: records.append((message.record["level"].name, message.record["message"])),
        level="DEBUG",
    )
    yield records
    logger.remove(handler_id)
