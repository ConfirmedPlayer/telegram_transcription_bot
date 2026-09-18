from utils.text import one_line, truncate_words


def test_short_text_is_unchanged():
    assert truncate_words("привет мир", 20) == "привет мир"


def test_cuts_on_word_boundary_and_fits_limit():
    result = truncate_words("один два три четыре", 12)
    assert result == "один два…"
    assert len(result) <= 12


def test_hard_cut_when_no_spaces():
    result = truncate_words("абвгдежзик", 5)
    assert result == "абвг…"
    assert len(result) == 5


def test_zero_limit_gives_empty_string():
    assert truncate_words("что угодно", 0) == ""


def test_one_line_collapses_whitespace():
    assert one_line("  раз\nдва\t\tтри  ") == "раз два три"
