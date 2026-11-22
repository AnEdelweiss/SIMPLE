"""Tests for the bounded retry helper and upload summary."""

from unittest.mock import MagicMock, patch

import opensilexClientToolsPython as silex
import pytest
import urllib3

from simple.upload import UploadSummary, is_retryable, with_retry


def test_with_retry_returns_on_first_success():
    call = MagicMock(return_value="ok")

    assert with_retry(call) == "ok"
    assert call.call_count == 1


def test_with_retry_retries_transient_errors():
    call = MagicMock(
        side_effect=[
            silex.rest.ApiException(status=503, reason="unavailable"),
            urllib3.exceptions.MaxRetryError(None, "/upload"),
            "ok",
        ]
    )

    with patch("simple.upload.time.sleep") as sleep:
        assert with_retry(call) == "ok"

    assert call.call_count == 3
    assert sleep.call_count == 2


def test_with_retry_does_not_retry_client_errors():
    call = MagicMock(
        side_effect=silex.rest.ApiException(status=401, reason="unauthorized")
    )

    with pytest.raises(silex.rest.ApiException):
        with_retry(call)

    assert call.call_count == 1


def test_with_retry_reraises_after_attempts():
    call = MagicMock(side_effect=OSError("connection reset"))

    with patch("simple.upload.time.sleep"):
        with pytest.raises(OSError):
            with_retry(call, attempts=2)

    assert call.call_count == 2


def test_is_retryable():
    assert is_retryable(silex.rest.ApiException(status=500, reason="boom"))
    assert is_retryable(silex.rest.ApiException(status=429, reason="slow down"))
    assert is_retryable(urllib3.exceptions.MaxRetryError(None, "/upload"))
    assert not is_retryable(silex.rest.ApiException(status=400, reason="bad request"))
    assert not is_retryable(FileNotFoundError("missing"))


def test_summary_merge_and_describe():
    first = UploadSummary(created=2, failed=1, skipped=3, failed_items=["a"])
    second = UploadSummary(created=4, failed=0, skipped=1, failed_items=["b"])

    assert first.merge(second) is first
    assert first.created == 6
    assert first.failed == 1
    assert first.skipped == 4
    assert first.failed_items == ["a", "b"]
    assert not first.ok
    assert first.describe() == "6 created, 1 failed, 4 already present"
