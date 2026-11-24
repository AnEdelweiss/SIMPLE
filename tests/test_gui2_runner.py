"""Qt-level cancellation test for the --gui2 import worker.

Skipped when the optional PyQt6 extra is not installed (as in CI).
"""

import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from simple.errors import ImportCancelled
from simple.upload import UploadSummary


def _spin(app, predicate, timeout=8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_import_thread_cancels_mid_phase():
    pytest.importorskip("PyQt6")
    from PyQt6.QtCore import QCoreApplication

    from simple.gui2.runner import ImportThread

    app = QCoreApplication.instance() or QCoreApplication([])
    state = {"in_tabular": False, "cancelled": False, "finished": False}

    def slow_tabular(*args, **kwargs):
        state["in_tabular"] = True
        should_cancel = kwargs.get("should_cancel")
        for _ in range(400):
            if should_cancel is not None and should_cancel():
                raise ImportCancelled("stopped by test")
            time.sleep(0.005)
        return SimpleNamespace(upload_summary=UploadSummary())

    session = SimpleNamespace(
        api_client=object(),
        login={},
        folder="/tmp",
        miappe="m.xlsx",
        tabular="d.xlsx",
        datafiles=None,
        report=None,
    )

    with (
        patch("simple.gui2.runner.create_experiment", return_value={"e": "u"}),
        patch("simple.gui2.runner.create_germplasm", return_value=({}, {})),
        patch("simple.gui2.runner.create_factor", return_value=({}, {})),
        patch("simple.gui2.runner.create_sci_obj", return_value=({}, 0)),
        patch("simple.gui2.runner.run_tabular_import", side_effect=slow_tabular),
    ):
        thread = ImportThread(session, has_datafiles=False)
        thread.cancelled.connect(lambda: state.__setitem__("cancelled", True))
        thread.finished_summary.connect(lambda _summary: state.__setitem__("finished", True))
        thread.start()

        assert _spin(app, lambda: state["in_tabular"]), "never reached tabular phase"
        thread.cancel()
        assert _spin(app, lambda: state["cancelled"]), "cancellation was not reported"
        assert not state["finished"], "cancelled run must not report success"
        thread.wait(3000)
        assert not thread.isRunning()
