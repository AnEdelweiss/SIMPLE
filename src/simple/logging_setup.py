import datetime
import logging
import os
import tempfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_FILE_FORMAT = logging.Formatter(
    "%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)


def _next_log_file(log_dir):
    """Return the path of the next unused per-day log file in ``log_dir``."""
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    counter = 1
    while True:
        path = os.path.join(log_dir, f"simple_app_{today}_{counter}.log")
        if not os.path.exists(path):
            return path
        counter += 1


def _resolve_log_dir():
    """Pick the first writable log directory, falling back to a temp dir."""
    candidates = (
        os.environ.get("SIMPLE_LOG_DIR"),
        os.path.join(BASE_DIR, "logs_SIMPLE"),
        os.path.join(tempfile.gettempdir(), "simple_logs"),
    )
    for candidate in candidates:
        if not candidate:
            continue
        try:
            os.makedirs(candidate, exist_ok=True)
            return candidate
        except OSError:
            continue
    return tempfile.gettempdir()


class _LazyFileHandler(logging.Handler):
    """Create the real FileHandler only on the first log record.

    ``logging_setup`` is imported by every module, so opening the log file at
    import time made ``import simple.auth`` raise PermissionError from any
    read-only location (system installs, containers, zipapps). The handler is
    installed lazily and picks the first writable directory instead.
    """

    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self._handler = None

    def _ensure(self):
        if self._handler is not None:
            return self._handler
        try:
            self._handler = logging.FileHandler(
                _next_log_file(_resolve_log_dir()), encoding="utf-8"
            )
            self._handler.setLevel(logging.DEBUG)
            self._handler.setFormatter(_FILE_FORMAT)
        except OSError:
            # Never let logging break the program; WARNING+ still reaches
            # stderr via logging.lastResort.
            self._handler = None
        return self._handler

    def emit(self, record):
        handler = self._ensure()
        if handler is not None:
            handler.emit(record)


logger = logging.getLogger("simple_logger")
logger.setLevel(logging.DEBUG)  # The core logger catches everything

if not logger.handlers:
    logger.addHandler(_LazyFileHandler())
