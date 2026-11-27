"""Tests for the Qt-free GUI text helpers."""

from simple.gui.text import clean_rich


def test_strips_known_rich_tags():
    assert clean_rich("[bold green][✓][/bold green] connected") == "[✓] connected"


def test_keeps_brackets_that_are_not_rich_tags():
    assert clean_rich("[INFO] row [1]") == "[INFO] row [1]"


def test_coerces_non_string_values():
    assert clean_rich(12) == "12"
