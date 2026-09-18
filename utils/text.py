"""Обрезка и нормализация текста для контекста и промпта."""


def truncate_words(text: str, limit: int) -> str:
    """Обрезать text до limit символов по границе слова.

    Если текст обрезан, в конце ставится «…», и итоговая длина не превышает limit.
    """
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    budget = limit - 1  # место под «…»
    cut = text.rfind(" ", 0, budget + 1)
    if cut <= 0:
        cut = budget
    return text[:cut].rstrip() + "…"


def one_line(text: str) -> str:
    """Схлопнуть переводы строк и повторные пробелы в один пробел."""
    return " ".join(text.split())
