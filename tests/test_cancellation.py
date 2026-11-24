"""Tests for the cooperative cancellation helper."""

import pytest

from simple.cancellation import check_cancelled
from simple.errors import ImportCancelled


def test_none_means_no_cancellation():
    check_cancelled(None)


def test_false_does_not_raise():
    check_cancelled(lambda: False)


def test_true_raises_import_cancelled():
    with pytest.raises(ImportCancelled, match="cancelled"):
        check_cancelled(lambda: True)
