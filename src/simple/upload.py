"""Shared upload helpers: bounded retries and a created/failed summary."""

import time
from dataclasses import dataclass, field

import opensilexClientToolsPython as silex
import urllib3

from simple.logging_setup import logger

RETRY_ATTEMPTS = 3
RETRY_DELAY = 1.0

# Errors worth retrying. Authentication/authorisation and client errors are
# not: retrying them just repeats the same rejection.
RETRYABLE_ERRORS = (silex.rest.ApiException, urllib3.exceptions.HTTPError, OSError)


def is_retryable(exc):
    if isinstance(exc, silex.rest.ApiException):
        status = exc.status
        return status is None or status == 429 or (
            isinstance(status, int) and status >= 500
        )
    if isinstance(exc, FileNotFoundError):
        return False
    return isinstance(exc, RETRYABLE_ERRORS)


def with_retry(call, *, attempts=RETRY_ATTEMPTS, delay=RETRY_DELAY, sleep=None):
    """Call *call* up to *attempts* times on retryable upload errors.

    The last exception is re-raised once the attempts are exhausted, so callers
    can record the failure and carry on with the rest of the import.
    """
    if sleep is None:
        sleep = time.sleep
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except RETRYABLE_ERRORS as exc:
            if not is_retryable(exc) or attempt >= attempts:
                raise
            logger.warning(
                f"Upload attempt {attempt}/{attempts} failed ({exc}); retrying..."
            )
            sleep(delay * attempt)
    raise AssertionError("unreachable")


@dataclass
class UploadSummary:
    """How many items an import created, failed and found already present."""

    created: int = 0
    failed: int = 0
    skipped: int = 0
    failed_items: list = field(default_factory=list)

    @property
    def ok(self):
        return self.failed == 0

    def merge(self, other):
        self.created += other.created
        self.failed += other.failed
        self.skipped += other.skipped
        self.failed_items.extend(other.failed_items)
        return self

    def describe(self):
        return (
            f"{self.created} created, {self.failed} failed, "
            f"{self.skipped} already present"
        )
