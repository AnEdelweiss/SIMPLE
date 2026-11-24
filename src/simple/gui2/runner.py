"""Background workers for the dashboard GUI.

The import sequence mirrors the CLI's "run all imports" order and reuses
``simple.import_service`` unchanged. A worker only surfaces progress and
results through signals; it never touches widgets.
"""

import logging

import pandas as pd
from PyQt6.QtCore import QThread, pyqtSignal

from simple.data_import import (
    create_factor,
    create_germplasm,
    create_sci_obj,
)
from simple.errors import ImportCancelled
from simple.experiment import create_experiment
from simple.gui2.widgets import clean_rich
from simple.import_service import (
    plan_datafiles_import,
    run_tabular_import,
    upload_datafiles,
)
from simple.logging_setup import logger
from simple.upload import UploadSummary


class TaskThread(QThread):
    """Run a plain callable off the UI thread."""

    done = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, func, parent=None):
        super().__init__(parent)
        self.func = func

    def run(self):
        try:
            self.done.emit(self.func())
        except Exception as exc:  # thread boundary: always report back
            logger.error(str(exc))
            self.error.emit(str(exc))


class _SignalHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        self.setLevel(logging.INFO)
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record):
        try:
            if record.levelno >= logging.ERROR:
                level = "error"
            elif record.levelno >= logging.WARNING:
                level = "warn"
            else:
                level = "info"
            self.signal.emit(level, clean_rich(record.getMessage()))
        except Exception:
            pass


def phase_keys(has_datafiles):
    """Ordered (key, label) pairs for the import checklist."""
    keys = [
        ("experiment", "Experiment"),
        ("germplasm", "Germplasms"),
        ("factors", "Factors"),
        ("scientific_objects", "Scientific objects"),
    ]
    if has_datafiles:
        keys.append(("datafiles", "Datafiles"))
    keys.append(("tabular", "Tabular data"))
    return keys


class ImportThread(QThread):
    """Run the full import and report every phase transition."""

    phase_started = pyqtSignal(str, str)
    phase_done = pyqtSignal(str, str)
    phase_failed = pyqtSignal(str, str)
    progress = pyqtSignal(str, str, int, int)  # phase, label, done, total
    log = pyqtSignal(str, str)
    finished_summary = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, session, has_datafiles, datafile_check=None, parent=None):
        super().__init__(parent)
        self.session = session
        self.has_datafiles = has_datafiles
        self.datafile_check = datafile_check
        self._cancelled = False
        self._plan = None
        self._sci_obj = None
        self._done = 0
        self._total = 0
        self._df_total = 0
        self._df_done = 0

    def cancel(self):
        self._cancelled = True

    def _should_cancel(self):
        return self._cancelled

    def _check_cancel(self):
        if self._cancelled:
            raise ImportCancelled("Import cancelled by the user.")

    def _status(self, message):
        self.log.emit("info", clean_rich(message))

    def _phase(self, key, label, func):
        self._check_cancel()
        self.phase_started.emit(key, label)
        try:
            detail = func()
        except ImportCancelled:
            raise
        except Exception as exc:
            self.phase_failed.emit(key, str(exc))
            raise
        self.phase_done.emit(key, detail or "")
        return detail

    # ---- individual phases -------------------------------------------------

    def _experiment(self):
        session = self.session
        result = create_experiment(
            session.miappe,
            session.api_client,
            status_callback=self._status,
            should_cancel=self._should_cancel,
        )
        name = next(iter(result), "experiment")
        return f"{name} created or found"

    def _germplasm(self):
        session = self.session
        germplasms, _species = create_germplasm(
            session.miappe,
            session.api_client,
            should_cancel=self._should_cancel,
        )
        return f"{len(germplasms)} processed"

    def _factors(self):
        session = self.session
        _levels, factors = create_factor(
            session.miappe,
            session.api_client,
            should_cancel=self._should_cancel,
        )
        return f"{len(factors)} processed"

    def _scientific_objects(self):
        session = self.session
        sci_obj_uri, created = create_sci_obj(
            session.tabular,
            session.miappe,
            session.api_client,
            status_callback=self._status,
            should_cancel=self._should_cancel,
        )
        self._sci_obj = (sci_obj_uri, created)
        found = len(sci_obj_uri) - created
        return f"{len(sci_obj_uri)} resolved ({found} found, {created} created)"

    def _datafile_progress(self, task_name, total=None, advance=0):
        if total:
            if total != self._df_total:
                self._df_total = total
                self._df_done = 0
        self._df_done += advance
        self.progress.emit(
            "datafiles", task_name, self._df_done, self._df_total
        )

    def _datafiles(self):
        session = self.session
        self._plan = plan_datafiles_import(
            session.miappe,
            session.tabular,
            session.folder,
            session.api_client,
            session.datafiles,
            confirm_create_default_provenances=lambda missing: True,
            confirm_protocol=lambda found: True,
            confirm_discrepancies=lambda missing1, missing2: True,
            confirm_upload=lambda: True,
            datafile_check=self.datafile_check,
            status_factory=None,
            sci_obj=self._sci_obj,
        )
        summary = upload_datafiles(
            self._plan,
            session.miappe,
            session.tabular,
            session.login,
            session.api_client,
            status_callback=self._status,
            progress_callback=self._datafile_progress,
            wrap_errors=False,
            should_cancel=self._should_cancel,
        )
        self._summary.merge(summary)
        return summary.describe()

    def _tabular(self):
        session = self.session

        def confirm_data_mapping(_morpho_info):
            try:
                total = len(_morpho_info) * len(pd.read_excel(session.tabular))
            except Exception:
                total = 0
            self._done = 0
            self._total = total
            self.progress.emit("tabular", "Uploading tabular data", 0, total)
            return True

        def show_progress(variable_name, line_count):
            self._done += line_count
            self.progress.emit(
                "tabular", f"Adding to {variable_name}", self._done, self._total
            )

        provenances = None
        if self._plan is not None:
            provenances = (self._plan.prov_dict, self._plan.datafile_provenance)
        result = run_tabular_import(
            session.tabular,
            session.miappe,
            session.login,
            session.api_client,
            confirm_data_mapping=confirm_data_mapping,
            confirm_create_default_provenances=lambda missing: True,
            progress_callback=show_progress,
            provenances=provenances,
            sci_obj=self._sci_obj,
            should_cancel=self._should_cancel,
        )
        self._summary.merge(result.upload_summary)
        return result.upload_summary.describe()

    # ---- thread body -------------------------------------------------------

    def run(self):
        handler = _SignalHandler(self.log)
        logger.addHandler(handler)
        self._summary = UploadSummary()
        try:
            self._phase("experiment", "Experiment", self._experiment)
            self._phase("germplasm", "Germplasms", self._germplasm)
            self._phase("factors", "Factors", self._factors)
            self._phase(
                "scientific_objects",
                "Scientific objects",
                self._scientific_objects,
            )
            if self.has_datafiles:
                self._phase("datafiles", "Datafiles", self._datafiles)
            self._phase("tabular", "Tabular data", self._tabular)
        except ImportCancelled:
            self.cancelled.emit()
        except Exception as exc:  # reported after phase_failed
            self.failed.emit(str(exc))
        else:
            self.finished_summary.emit(self._summary)
        finally:
            logger.removeHandler(handler)
