"""Cooperative cancellation for long-running import loops.

The backend never reads the user interface directly: callers inject a
zero-argument ``should_cancel`` callable. This keeps the loops testable and
lets the CLI ignore cancellation entirely (``None``).
"""

from simple.errors import ImportCancelled


def check_cancelled(should_cancel):
    """Raise :class:`ImportCancelled` when *should_cancel* reports ``True``.

    ``None`` means cancellation was not requested by the caller.
    """
    if should_cancel is not None and should_cancel():
        raise ImportCancelled("Import cancelled by the user.")
