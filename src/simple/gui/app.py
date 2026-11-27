"""Graphical interface for SIMPLE (launched with ``simple --gui``)."""

import os
import sys
from dataclasses import dataclass, field

import opensilexClientToolsPython as silex
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from simple import __version__
from simple.auth import INSTANCES, SANDBOX_URL, connect
from simple.gui import discovery
from simple.gui.runner import ImportThread, TaskThread, phase_keys
from simple.gui.theme import QSS
from simple.gui.widgets import (
    Card,
    CheckRow,
    FileRow,
    LogDialog,
    LogView,
    MetricTile,
    Pill,
    Sidebar,
    clean_rich,
    label,
)


@dataclass
class Session:
    api_client: object
    login: dict | None = None
    connected: bool = False
    host_label: str = ""
    folder: str | None = None
    miappe: str | None = None
    tabular: str | None = None
    datafiles: str | None = None
    discovery: object = None
    report: object = None
    validated: bool = False
    summary: object = None
    log_entries: list = field(default_factory=list)


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def short_path(path):
    if not path:
        return "—"
    home = os.path.expanduser("~")
    if path.startswith(home):
        return "~" + path[len(home):]
    return path


class ConnectPage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._thread = None

        page = QVBoxLayout(self)
        page.setContentsMargins(28, 22, 28, 18)
        page.setSpacing(14)

        page.addWidget(label("Connect", "title"))
        page.addWidget(
            label("Choose an instance and sign in. The Sandbox uses a guest account.", "subtitle")
        )

        card = Card()
        card.setFixedWidth(500)
        card.body.addWidget(label("INSTANCE", "cardtitle"))
        self.instance = QComboBox()
        self._instance_names = list(INSTANCES.values())
        self.instance.addItems(self._instance_names + ["Custom URL…"])
        card.body.addWidget(self.instance)

        self.custom = QLineEdit()
        self.custom.setPlaceholderText("https://my-phis.example/rest")
        self.custom.setVisible(False)
        card.body.addWidget(self.custom)

        card.body.addSpacing(4)
        card.body.addWidget(label("IDENTIFIER", "cardtitle"))
        self.user = QLineEdit()
        self.user.setPlaceholderText("name@example.org")
        card.body.addWidget(self.user)

        card.body.addSpacing(4)
        card.body.addWidget(label("PASSWORD", "cardtitle"))
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        card.body.addWidget(self.password)

        self.remember = QCheckBox("Remember this instance and user")
        card.body.addWidget(self.remember)

        self.hint = label("", "faint", wrap=True)
        card.body.addWidget(self.hint)

        self.status = label("Not connected.", "muted", wrap=True)
        card.body.addWidget(self.status)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setObjectName("primary")
        self.connect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.connect_btn.clicked.connect(self._connect)
        row = QHBoxLayout()
        row.addWidget(self.connect_btn)
        row.addStretch(1)
        card.body.addLayout(row)

        wrapper = QHBoxLayout()
        wrapper.addWidget(card, 0, Qt.AlignmentFlag.AlignTop)
        wrapper.addStretch(1)
        page.addLayout(wrapper)
        page.addStretch(1)

        self.instance.currentIndexChanged.connect(self._instance_changed)
        self.custom.textChanged.connect(lambda _text: self._instance_changed())
        self._instance_changed()

    def _instance_changed(self):
        custom = self.instance.currentText() == "Custom URL…"
        self.custom.setVisible(custom)
        host = self.custom.text().strip() if custom else self._host()
        sandbox = host == SANDBOX_URL and not custom
        self.user.setEnabled(not sandbox)
        self.password.setEnabled(not sandbox)
        self.user.setPlaceholderText(
            "guest (automatic)" if sandbox else "name@example.org"
        )
        self.hint.setText(
            "Guest login is automatic on the Sandbox."
            if sandbox
            else "Your credentials are only sent to the selected instance."
        )
        self.connect_btn.setText("Reconnect" if self.controller.session.connected else "Connect")

    def _host(self):
        name = self.instance.currentText()
        for url, label_text in INSTANCES.items():
            if label_text == name:
                return url
        return self.custom.text().strip()

    def on_show(self):
        session = self.controller.session
        if session.connected:
            self.status.setText(f"Connected: {session.host_label}")
            self.status.setStyleSheet("color: #2e7d4f;")
        else:
            self.status.setText("Not connected.")
            self.status.setStyleSheet("")
        self.connect_btn.setText("Reconnect" if session.connected else "Connect")

    def _connect(self):
        session = self.controller.session
        host = self._host()
        if not host:
            self._fail("Enter the instance REST URL.")
            return
        if host == SANDBOX_URL:
            login = {
                "host": host,
                "identifier": "guest@opensilex.org",
                "password": "guest",
            }
        else:
            identifier = self.user.text().strip()
            password = self.password.text()
            if not identifier:
                self._fail("Enter your identifier.")
                return
            login = {"host": host, "identifier": identifier, "password": password}

        self.connect_btn.setEnabled(False)
        self.status.setText("Connecting…")
        self.status.setStyleSheet("")

        thread = TaskThread(lambda: connect(login, session.api_client), self)
        self._thread = thread
        thread.done.connect(lambda ok: self._connected(login, host))
        thread.error.connect(self._fail)
        thread.start()

    def _connected(self, login, host):
        session = self.controller.session
        session.connected = True
        session.login = login
        display = INSTANCES.get(host, host)
        session.host_label = f"{display} · {login['identifier']}"
        self.connect_btn.setEnabled(True)
        self.status.setText(f"Connected: {session.host_label}")
        self.status.setStyleSheet("color: #2e7d4f;")

        settings = self.controller.settings
        settings.setValue("instance", host)
        settings.setValue("remember", self.remember.isChecked())
        if self.remember.isChecked():
            settings.setValue("user", login["identifier"])
        self.controller.refresh()
        self.controller.go(1)

    def _fail(self, message):
        self.connect_btn.setEnabled(True)
        self.status.setText(message)
        self.status.setStyleSheet("color: #b91c1c;")
        self.controller.append_log("error", message)
        QMessageBox.critical(self, "Connection failed", str(message))


class ExperimentPage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        page = QVBoxLayout(self)
        page.setContentsMargins(28, 22, 28, 18)
        page.setSpacing(14)

        page.addWidget(label("Experiment", "title"))
        page.addWidget(
            label(
                "Pick the folder that holds the MIAPPE template, the tabular data "
                "and the datafiles.",
                "subtitle",
            )
        )

        folder_card = Card()
        head = QHBoxLayout()
        head.addWidget(label("WORKING FOLDER", "cardtitle"))
        head.addStretch(1)
        self.browse = QPushButton("Choose folder…")
        self.browse.setObjectName("ghost")
        self.browse.clicked.connect(self._browse)
        head.addWidget(self.browse)
        folder_card.body.addLayout(head)
        self.folder_value = label("No folder selected", "mono", wrap=True)
        folder_card.body.addWidget(self.folder_value)
        self.status = label("", "faint", wrap=True)
        folder_card.body.addWidget(self.status)
        page.addWidget(folder_card)

        self.found = Card()
        self.found.body.addWidget(label("FOUND IN THIS FOLDER", "cardtitle"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)
        self.name_value = label("—", "mono")
        self.miappe_value = label("—", "mono", wrap=True)
        grid.addWidget(label("Experiment", "faint"), 0, 0)
        grid.addWidget(self.name_value, 0, 1)
        grid.addWidget(label("MIAPPE template", "faint"), 1, 0)
        grid.addWidget(self.miappe_value, 1, 1)
        grid.addWidget(label("Tabular data", "faint"), 2, 0)
        self.tabular_combo = QComboBox()
        grid.addWidget(self.tabular_combo, 2, 1)
        grid.addWidget(label("Datafiles", "faint"), 3, 0)
        self.datafiles_combo = QComboBox()
        grid.addWidget(self.datafiles_combo, 3, 1)
        grid.setColumnStretch(1, 1)
        self.found.body.addLayout(grid)
        self.found.setVisible(False)
        page.addWidget(self.found)

        page.addStretch(1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        self.continue_btn = QPushButton("Continue")
        self.continue_btn.setObjectName("primary")
        self.continue_btn.clicked.connect(lambda: self.controller.go(2))
        footer.addWidget(self.continue_btn)
        page.addLayout(footer)

        self.tabular_combo.currentIndexChanged.connect(self._tabular_changed)
        self.datafiles_combo.currentIndexChanged.connect(self._datafiles_changed)

    def _browse(self):
        start = self.controller.session.folder or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, "Select experiment folder", start)
        if folder:
            self.controller.set_folder(folder)

    def _tabular_changed(self):
        value = self.tabular_combo.currentData()
        if value and value != self.controller.session.tabular:
            self.controller.set_tabular(value)

    def _datafiles_changed(self):
        value = self.datafiles_combo.currentData()
        if value is not None and value != self.controller.session.datafiles:
            self.controller.set_datafiles(value)

    def refresh(self):
        session = self.controller.session
        discovered = session.discovery
        self.folder_value.setText(short_path(session.folder) if session.folder else "No folder selected")
        self.continue_btn.setEnabled(bool(session.folder))

        if not discovered:
            self.found.setVisible(False)
            self.status.setText("")
            return

        self.found.setVisible(True)
        self.name_value.setText(discovered.experiment_name or "—")
        self.miappe_value.setText(
            os.path.basename(session.miappe) if session.miappe else "not found"
        )

        self.tabular_combo.blockSignals(True)
        self.tabular_combo.clear()
        for path in discovered.tabular_candidates:
            self.tabular_combo.addItem(os.path.basename(path), path)
        if session.tabular:
            index = self.tabular_combo.findData(session.tabular)
            if index >= 0:
                self.tabular_combo.setCurrentIndex(index)
        self.tabular_combo.blockSignals(False)

        self.datafiles_combo.blockSignals(True)
        self.datafiles_combo.clear()
        for path in discovered.datafiles_candidates:
            self.datafiles_combo.addItem(short_path(path), path)
        if session.datafiles:
            index = self.datafiles_combo.findData(session.datafiles)
            if index >= 0:
                self.datafiles_combo.setCurrentIndex(index)
        self.datafiles_combo.blockSignals(False)

        if discovered.error:
            self.status.setText(discovered.error)
            self.status.setStyleSheet("color: #b91c1c;")
        elif not discovered.tabular_candidates:
            self.status.setText("No tabular data file found in this folder.")
            self.status.setStyleSheet("color: #b45309;")
        else:
            count = len(discovered.tabular_candidates)
            self.status.setText(
                f"{count} tabular file(s) found. Pick another one if needed."
            )
            self.status.setStyleSheet("color: #6b7280;")

    def on_show(self):
        self.refresh()


class FilesPage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        page = QVBoxLayout(self)
        page.setContentsMargins(28, 22, 28, 18)
        page.setSpacing(14)

        page.addWidget(label("Files", "title"))
        page.addWidget(
            label("Confirm the files SIMPLE will use. Change any of them here.", "subtitle")
        )

        card = Card(spacing=12)
        self.folder_row = FileRow("Working folder")
        self.miappe_row = FileRow("MIAPPE template")
        self.tabular_row = FileRow("Tabular data")
        self.datafiles_row = FileRow("Datafiles")
        for row in (
            self.folder_row,
            self.miappe_row,
            self.tabular_row,
            self.datafiles_row,
        ):
            card.body.addWidget(row)
        page.addWidget(card)

        self.hint = label("", "faint", wrap=True)
        page.addWidget(self.hint)
        page.addStretch(1)

        footer = QHBoxLayout()
        back = QPushButton("Back")
        back.setObjectName("ghost")
        back.clicked.connect(lambda: self.controller.go(1))
        footer.addWidget(back)
        footer.addStretch(1)
        self.continue_btn = QPushButton("Continue")
        self.continue_btn.setObjectName("primary")
        self.continue_btn.clicked.connect(lambda: self.controller.go(3))
        footer.addWidget(self.continue_btn)
        page.addLayout(footer)

        self.folder_row.change_requested.connect(self._change_folder)
        self.miappe_row.change_requested.connect(self._change_miappe)
        self.tabular_row.change_requested.connect(self._change_tabular)
        self.datafiles_row.change_requested.connect(self._change_datafiles)

    def _start_dir(self):
        session = self.controller.session
        return session.folder or os.path.expanduser("~")

    def _change_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select experiment folder", self._start_dir()
        )
        if folder:
            self.controller.set_folder(folder)

    def _change_miappe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select MIAPPE template", self._start_dir(), "Excel files (*.xlsx *.xls)"
        )
        if path:
            self.controller.set_miappe(path)

    def _change_tabular(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select tabular data", self._start_dir(), "Excel files (*.xlsx *.xls)"
        )
        if path:
            self.controller.set_tabular(path)

    def _change_datafiles(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select datafiles folder", self._start_dir()
        )
        if path:
            self.controller.set_datafiles(path)

    def refresh(self):
        session = self.controller.session
        self.folder_row.set_value(short_path(session.folder) if session.folder else "—")
        self.miappe_row.set_value(
            os.path.basename(session.miappe) if session.miappe else "—"
        )
        self.tabular_row.set_value(
            os.path.basename(session.tabular) if session.tabular else "—"
        )
        self.datafiles_row.set_value(
            short_path(session.datafiles) if session.datafiles else "—"
        )
        for row, value in (
            (self.folder_row, session.folder),
            (self.miappe_row, session.miappe),
            (self.tabular_row, session.tabular),
            (self.datafiles_row, session.datafiles),
        ):
            row.value.setToolTip(short_path(value) if value else "")

        ready = bool(session.miappe and session.tabular)
        self.continue_btn.setEnabled(ready)
        if ready:
            self.hint.setText("Ready to validate.")
            self.hint.setStyleSheet("color: #6b7280;")
        else:
            missing = []
            if not session.miappe:
                missing.append("MIAPPE template")
            if not session.tabular:
                missing.append("tabular data")
            self.hint.setText(f"Still needed: {', '.join(missing)}.")
            self.hint.setStyleSheet("color: #b45309;")

    def on_show(self):
        self.refresh()


class ValidatePage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._thread = None
        self._ran_for = None
        self._running = False

        page = QVBoxLayout(self)
        page.setContentsMargins(28, 22, 28, 18)
        page.setSpacing(14)

        page.addWidget(label("Validate", "title"))
        page.addWidget(
            label(
                "Offline checks of the template, the tabular data and the datafiles. "
                "Nothing is uploaded here.",
                "subtitle",
            )
        )

        card = Card(spacing=10)
        head = QHBoxLayout()
        head.addWidget(label("PREFLIGHT CHECKS", "cardtitle"))
        head.addStretch(1)
        self.passed = label("", "faint")
        head.addWidget(self.passed)
        card.body.addLayout(head)
        self.list_box = QVBoxLayout()
        self.list_box.setSpacing(9)
        card.body.addLayout(self.list_box)
        page.addWidget(card)

        self.status = label("", "faint", wrap=True)
        page.addWidget(self.status)
        page.addStretch(1)

        footer = QHBoxLayout()
        self.run_btn = QPushButton("Run checks again")
        self.run_btn.setObjectName("ghost")
        self.run_btn.clicked.connect(self.run_checks)
        footer.addWidget(self.run_btn)
        footer.addStretch(1)
        back = QPushButton("Back")
        back.setObjectName("ghost")
        back.clicked.connect(lambda: self.controller.go(2))
        footer.addWidget(back)
        self.continue_btn = QPushButton("Continue")
        self.continue_btn.setObjectName("primary")
        self.continue_btn.clicked.connect(lambda: self.controller.go(4))
        footer.addWidget(self.continue_btn)
        page.addLayout(footer)

    def _paths(self):
        session = self.controller.session
        return (session.miappe, session.tabular, session.datafiles)

    def on_show(self):
        if not self._running and self._ran_for != self._paths():
            self.run_checks()
        else:
            self._render()

    def run_checks(self):
        session = self.controller.session
        if not (session.miappe and session.tabular):
            return
        self._running = True
        self.run_btn.setEnabled(False)
        self.continue_btn.setEnabled(False)
        self.passed.setText("")
        self.status.setText("Running checks…")
        self.status.setStyleSheet("color: #6b7280;")
        clear_layout(self.list_box)
        self.list_box.addWidget(CheckRow("Reading the template and data files…", "info"))

        miappe, tabular, datafiles = self._paths()
        thread = TaskThread(
            lambda: discovery.validate_all(
                session.folder, miappe, tabular, datafiles
            ),
            self,
        )
        self._thread = thread
        thread.done.connect(self._done)
        thread.error.connect(self._failed)
        thread.start()

    def _done(self, report):
        self._running = False
        session = self.controller.session
        session.report = report
        session.validated = not report.blocking
        self._ran_for = self._paths()
        self.run_btn.setEnabled(True)
        self.controller.refresh()
        self._render()

    def _failed(self, message):
        self._running = False
        self.run_btn.setEnabled(True)
        self.status.setText(message)
        self.status.setStyleSheet("color: #b91c1c;")
        clear_layout(self.list_box)
        self.list_box.addWidget(CheckRow(message, "error"))
        self.controller.append_log("error", message)

    def _render(self):
        session = self.controller.session
        report = session.report
        clear_layout(self.list_box)
        if report is None:
            self.list_box.addWidget(CheckRow("No checks have run yet.", "info"))
            return
        for check in report.checks:
            self.list_box.addWidget(CheckRow(check.text, check.level))
        bits = []
        if report.passed:
            bits.append(f"{report.passed} passed")
        if report.warnings:
            bits.append(f"{report.warnings} warning(s)")
        if report.errors:
            bits.append(f"{report.errors} error(s)")
        self.passed.setText(" · ".join(bits))
        self.passed.setStyleSheet(
            f"color: {('#b91c1c' if report.errors else '#b45309' if report.warnings else '#2e7d4f')};"
            "font-weight: 700; font-size: 12px;"
        )
        self.continue_btn.setEnabled(not report.blocking)
        if report.blocking:
            self.status.setText("Fix the errors above before continuing.")
            self.status.setStyleSheet("color: #b91c1c;")
        elif report.warnings:
            self.status.setText(
                "Warnings will not block the import; the affected items are skipped."
            )
            self.status.setStyleSheet("color: #b45309;")
        else:
            self.status.setText("Everything looks good.")
            self.status.setStyleSheet("color: #2e7d4f;")


class ImportPage(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.thread = None
        self.step_widgets = {}
        self._build()

    # ---- construction ------------------------------------------------------

    def _build(self):
        page = QVBoxLayout(self)
        page.setContentsMargins(0, 0, 0, 0)

        self.view = QStackedWidget()
        self.review = self._build_review()
        self.running = self._build_running()
        self.done = self._build_done()
        self.view.addWidget(self.review)
        self.view.addWidget(self.running)
        self.view.addWidget(self.done)
        page.addWidget(self.view)

    def _build_review(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(28, 22, 28, 18)
        box.setSpacing(14)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("Review & import", "title"))
        titles.addWidget(
            label(
                "Everything is ready. Check the plan below, then start the import.",
                "subtitle",
            )
        )
        head.addLayout(titles, 1)
        self.review_pill = Pill("Ready to import", "ok")
        head.addWidget(self.review_pill, 0, Qt.AlignmentFlag.AlignTop)
        box.addLayout(head)

        context, context_body = Card(), None
        context_body = context.body
        ctx_head = QHBoxLayout()
        ctx_head.addWidget(label("EXPERIMENT CONTEXT", "cardtitle"))
        ctx_head.addStretch(1)
        change = QPushButton("Change files")
        change.setObjectName("link")
        change.clicked.connect(lambda: self.controller.go(2))
        ctx_head.addWidget(change)
        context_body.addLayout(ctx_head)
        self.context_rows = {
            "folder": FileRow("Working folder"),
            "miappe": FileRow("MIAPPE template"),
            "tabular": FileRow("Tabular data"),
            "datafiles": FileRow("Datafiles"),
        }
        for row in self.context_rows.values():
            row.set_change_visible(False)
            context_body.addWidget(row)
        box.addWidget(context)

        metrics, metrics_body = Card(), None
        metrics_body = metrics.body
        metrics_body.addWidget(label("WHAT WILL BE CREATED", "cardtitle"))
        metric_row = QHBoxLayout()
        metric_row.setSpacing(10)
        self.tiles = {}
        for key, caption in (
            ("experiment", "Experiment"),
            ("germplasms", "Germplasms"),
            ("factors", "Factors"),
            ("sci_objects", "Scientific objects"),
            ("datafiles", "Datafiles"),
            ("rows", "Data rows"),
        ):
            tile = MetricTile("—", caption)
            self.tiles[key] = tile
            metric_row.addWidget(tile, 1)
        metrics_body.addLayout(metric_row)
        box.addWidget(metrics)

        checks, checks_body = Card(), None
        checks_body = checks.body
        checks_head = QHBoxLayout()
        checks_head.addWidget(label("PREFLIGHT CHECKS", "cardtitle"))
        checks_head.addStretch(1)
        self.review_checks_meta = label("", "faint")
        checks_head.addWidget(self.review_checks_meta)
        checks_body.addLayout(checks_head)
        self.review_checks = QVBoxLayout()
        self.review_checks.setSpacing(9)
        checks_body.addLayout(self.review_checks)
        box.addWidget(checks)

        box.addStretch(1)

        note = label(
            "Imports run in this order: experiment, germplasm, factors, scientific "
            "objects, datafiles, tabular data. You can stop between steps.",
            "faint",
            wrap=True,
        )
        note.setStyleSheet(
            "background: #eef2f5; color: #4b5563; border-radius: 8px;"
            "padding: 10px 14px; font-size: 12px;"
        )
        box.addWidget(note)

        footer = QHBoxLayout()
        view_log = QPushButton("View log")
        view_log.setObjectName("ghost")
        view_log.clicked.connect(self.controller.view_log)
        footer.addWidget(view_log)
        back = QPushButton("Back")
        back.setObjectName("ghost")
        back.clicked.connect(lambda: self.controller.go(3))
        footer.addWidget(back)
        footer.addStretch(1)
        self.run_btn = QPushButton("Run import")
        self.run_btn.setObjectName("primary")
        self.run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_btn.clicked.connect(self.start_import)
        footer.addWidget(self.run_btn)
        box.addLayout(footer)
        return page

    def _build_running(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(28, 22, 28, 18)
        box.setSpacing(14)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("Importing data", "title"))
        titles.addWidget(
            label(
                "Keep this window open. Cancel stops after the item in flight; "
                "completed items stay uploaded.",
                "subtitle",
            )
        )
        box.addLayout(titles)

        progress, progress_body = Card(), None
        progress_body = progress.body
        top = QHBoxLayout()
        self.phase_label = label("Starting…", "cardtitle")
        top.addWidget(self.phase_label)
        top.addStretch(1)
        self.count_label = label("", "muted")
        top.addWidget(self.count_label)
        progress_body.addLayout(top)
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(10)
        self.bar.setRange(0, 0)
        progress_body.addWidget(self.bar)
        sub = QHBoxLayout()
        self.eta_label = label("Working…", "faint")
        sub.addWidget(self.eta_label)
        sub.addStretch(1)
        self.cancel_btn = QPushButton("Cancel import")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.clicked.connect(self.cancel_import)
        sub.addWidget(self.cancel_btn)
        progress_body.addLayout(sub)
        box.addWidget(progress)

        steps, steps_body = Card(), None
        steps_body = steps.body
        steps_body.addWidget(label("IMPORT STEPS", "cardtitle"))
        self.steps_box = QVBoxLayout()
        self.steps_box.setSpacing(8)
        steps_body.addLayout(self.steps_box)
        box.addWidget(steps)

        activity, activity_body = Card(), None
        activity_body = activity.body
        act_head = QHBoxLayout()
        act_head.addWidget(label("RECENT ACTIVITY", "cardtitle"))
        act_head.addStretch(1)
        view = QPushButton("View full log")
        view.setObjectName("link")
        view.clicked.connect(self.controller.view_log)
        act_head.addWidget(view)
        activity_body.addLayout(act_head)
        self.activity_view = LogView()
        self.activity_view.setFixedHeight(84)
        self.activity_view.setStyleSheet(
            "QPlainTextEdit#log { background: #fafbfc; color: #4b5563;"
            " border: 1px solid #e5e7eb; border-radius: 8px;"
            " font-family: 'JetBrains Mono', monospace; font-size: 11px;"
            " padding: 8px; }"
        )
        activity_body.addWidget(self.activity_view)
        box.addWidget(activity)

        box.addStretch(1)

        footer = QHBoxLayout()
        footer.addWidget(label("Uploads are retried up to 3 times.", "faint"))
        footer.addStretch(1)
        box.addLayout(footer)
        return page

    def _build_done(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(28, 22, 28, 18)
        box.setSpacing(14)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("Import finished", "title"))
        self.done_sub = label("", "subtitle")
        titles.addWidget(self.done_sub)
        head.addLayout(titles, 1)
        self.done_pill = Pill("Done", "ok")
        head.addWidget(self.done_pill, 0, Qt.AlignmentFlag.AlignTop)
        box.addLayout(head)

        summary, summary_body = Card(), None
        summary_body = summary.body
        summary_body.addWidget(label("RESULT", "cardtitle"))
        grid = QHBoxLayout()
        grid.setSpacing(28)
        self.done_created = label("0", "metric")
        self.done_failed = label("0", "metric")
        self.done_skipped = label("0", "metric")
        for caption, value in (
            ("created", self.done_created),
            ("failed", self.done_failed),
            ("already present", self.done_skipped),
        ):
            column = QVBoxLayout()
            column.addWidget(value)
            column.addWidget(label(caption, "metriclabel"))
            grid.addLayout(column)
        grid.addStretch(1)
        summary_body.addLayout(grid)
        self.failed_list = QVBoxLayout()
        self.failed_list.setSpacing(6)
        summary_body.addLayout(self.failed_list)
        box.addWidget(summary)

        box.addStretch(1)

        footer = QHBoxLayout()
        view_log = QPushButton("View log")
        view_log.setObjectName("ghost")
        view_log.clicked.connect(self.controller.view_log)
        footer.addWidget(view_log)
        footer.addStretch(1)
        again = QPushButton("Import another file")
        again.setObjectName("ghost")
        again.clicked.connect(self.import_another)
        footer.addWidget(again)
        finish = QPushButton("Close")
        finish.setObjectName("primary")
        finish.clicked.connect(self.controller.close)
        footer.addWidget(finish)
        box.addLayout(footer)
        return page

    # ---- review ------------------------------------------------------------

    def refresh_review(self):
        session = self.controller.session
        report = session.report
        counts = report.counts if report else None

        self.context_rows["folder"].set_value(
            short_path(session.folder) if session.folder else "—"
        )
        self.context_rows["miappe"].set_value(
            os.path.basename(session.miappe) if session.miappe else "—"
        )
        self.context_rows["tabular"].set_value(
            os.path.basename(session.tabular) if session.tabular else "—"
        )
        self.context_rows["datafiles"].set_value(
            short_path(session.datafiles) if session.datafiles else "—"
        )

        values = {
            "experiment": 1 if session.miappe else "—",
            "germplasms": counts.germplasms if counts else "—",
            "factors": counts.factors if counts else "—",
            "sci_objects": counts.sci_objects if counts else "—",
            "datafiles": counts.datafiles if counts else "—",
            "rows": counts.rows if counts else "—",
        }
        for key, value in values.items():
            self.tiles[key].set_value(value)

        clear_layout(self.review_checks)
        if report:
            order = {"error": 0, "warn": 1, "ok": 2}
            ordered = sorted(report.checks, key=lambda check: order.get(check.level, 3))
            for check in ordered[:4]:
                self.review_checks.addWidget(CheckRow(check.text, check.level))
            bits = []
            if report.passed:
                bits.append(f"{report.passed} passed")
            if report.warnings:
                bits.append(f"{report.warnings} warning(s)")
            self.review_checks_meta.setText(" · ".join(bits))
            self.review_checks_meta.setStyleSheet(
                f"color: {('#b45309' if report.warnings else '#2e7d4f')};"
                "font-weight: 700; font-size: 12px;"
            )
            ready = not report.blocking
        else:
            self.review_checks.addWidget(CheckRow("No checks have run yet.", "info"))
            self.review_checks_meta.setText("")
            ready = False

        self.review_pill.setText("Ready to import" if ready else "Checks needed")
        self.review_pill.set_tone("ok" if ready else "warn")
        self.run_btn.setEnabled(ready)

    # ---- import lifecycle --------------------------------------------------

    def on_show(self):
        if self.controller.session.summary is not None:
            self._render_done()
            self.view.setCurrentWidget(self.done)
        elif self.thread is not None and self.thread.isRunning():
            self.view.setCurrentWidget(self.running)
        else:
            self.refresh_review()
            self.view.setCurrentWidget(self.review)

    def _has_datafiles(self):
        session = self.controller.session
        report = session.report
        return bool(
            session.datafiles
            and report
            and report.counts.has_file_column
        )

    def _build_steps(self):
        clear_layout(self.steps_box)
        self.step_widgets = {}
        for key, text in phase_keys(self._has_datafiles()):
            row = QWidget()
            box = QHBoxLayout(row)
            box.setContentsMargins(0, 2, 0, 2)
            box.setSpacing(10)
            bubble = QLabel("○")
            bubble.setFixedSize(20, 20)
            bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bubble.setStyleSheet(
                "background: #eef0f3; color: #9ca3af; border-radius: 10px;"
            )
            box.addWidget(bubble)
            name = label(text)
            name.setStyleSheet("font-weight: 600; color: #9ca3af;")
            box.addWidget(name)
            box.addStretch(1)
            detail = label("waiting", "faint")
            box.addWidget(detail)
            self.steps_box.addWidget(row)
            self.step_widgets[key] = (bubble, name, detail)

    def _set_step(self, key, state, detail=None):
        widgets = self.step_widgets.get(key)
        if not widgets:
            return
        bubble, name, detail_label = widgets
        styles = {
            "done": ("✓", "#e8f3ec", "#2e7d4f", "#6b7280", "600"),
            "active": ("●", "#2e7d4f", "#ffffff", "#111827", "700"),
            "error": ("✗", "#fdeaea", "#b91c1c", "#b91c1c", "700"),
            "pending": ("○", "#eef0f3", "#9ca3af", "#9ca3af", "600"),
        }
        glyph, background, foreground, name_color, weight = styles.get(
            state, styles["pending"]
        )
        bubble.setText(glyph)
        bubble.setStyleSheet(
            f"background: {background}; color: {foreground}; border-radius: 10px;"
        )
        name.setStyleSheet(f"font-weight: {weight}; color: {name_color};")
        if detail is not None:
            detail_label.setText(detail)

    def start_import(self):
        session = self.controller.session
        if session.summary is not None or (self.thread and self.thread.isRunning()):
            return
        self._build_steps()
        self.activity_view.clear()
        session.log_entries.clear()
        self.controller.append_log("info", "Import started.")
        self.phase_label.setText("Starting…")
        self.count_label.setText("")
        self.eta_label.setText("Working…")
        self.bar.setRange(0, 0)
        self.cancel_btn.setEnabled(True)

        has_datafiles = self._has_datafiles()
        check = session.report.datafile_check if session.report else None
        thread = ImportThread(session, has_datafiles, datafile_check=check, parent=self)
        self.thread = thread
        thread.phase_started.connect(self._phase_started)
        thread.phase_done.connect(self._phase_done)
        thread.phase_failed.connect(self._phase_failed)
        thread.progress.connect(self._progress)
        thread.log.connect(self._log)
        thread.finished_summary.connect(self._finished)
        thread.failed.connect(self._failed)
        thread.cancelled.connect(self._cancelled)
        self.view.setCurrentWidget(self.running)
        self.controller.set_busy(True)
        thread.start()

    def _phase_started(self, key, text):
        self._set_step(key, "active", "running…")
        self.phase_label.setText(text)
        self.count_label.setText("")
        self.bar.setRange(0, 0)

    def _phase_done(self, key, detail):
        self._set_step(key, "done", detail or "done")

    def _phase_failed(self, key, message):
        self._set_step(key, "error", "failed")
        self.phase_label.setText("Import failed")
        self.bar.setRange(0, 1)
        self.bar.setValue(0)
        self.controller.append_log("error", message)

    def _progress(self, key, text, done, total):
        self.phase_label.setText(text)
        if total <= 0:
            self.bar.setRange(0, 0)
            self.count_label.setText(f"{done}" if done else "")
        else:
            self.bar.setRange(0, total)
            self.bar.setValue(done)
            self.count_label.setText(f"{done} / {total}")

    def _log(self, level, message):
        self.controller.append_log(level, message)
        self.activity_view.append_entry(level, message)

    def _finished(self, summary):
        self.controller.session.summary = summary
        self.controller.set_busy(False)
        self.thread = None
        self._render_done()
        self.view.setCurrentWidget(self.done)
        self.controller.refresh()

    def _failed(self, message):
        self.controller.set_busy(False)
        self.thread = None
        self.controller.append_log("error", message)
        QMessageBox.critical(self, "Import failed", message)
        self.controller.refresh()
        self.refresh_review()
        self.view.setCurrentWidget(self.review)

    def _cancelled(self):
        self.controller.set_busy(False)
        self.thread = None
        self.controller.append_log("warn", "Import cancelled.")
        QMessageBox.information(
            self,
            "Cancelled",
            "The import was cancelled. Items already uploaded remain on the "
            "instance; running the import again is safe and skips what exists.",
        )
        self.controller.refresh()
        self.refresh_review()
        self.view.setCurrentWidget(self.review)

    def cancel_import(self):
        if self.thread and self.thread.isRunning():
            self.thread.cancel()
            self.cancel_btn.setEnabled(False)
            self.eta_label.setText("Stopping after the current item…")

    def _render_done(self):
        summary = self.controller.session.summary
        if summary is None:
            return
        self.done_created.setText(str(summary.created))
        self.done_failed.setText(str(summary.failed))
        self.done_skipped.setText(str(summary.skipped))
        self.done_failed.setStyleSheet(
            f"font-size: 22px; font-weight: 700; color: {'#b91c1c' if summary.failed else '#111827'};"
        )
        clear_layout(self.failed_list)
        if summary.failed:
            self.done_sub.setText("Some items failed. See the log for details.")
            self.done_pill.setText("Finished with failures")
            self.done_pill.set_tone("warn")
            self.failed_list.addWidget(label("FAILED ITEMS", "cardtitle"))
            for item in summary.failed_items[:10]:
                self.failed_list.addWidget(
                    CheckRow(str(item), "error")
                )
            if len(summary.failed_items) > 10:
                self.failed_list.addWidget(
                    label(
                        f"+{len(summary.failed_items) - 10} more in the log",
                        "faint",
                    )
                )
        else:
            self.done_sub.setText("Everything was created or found.")
            self.done_pill.setText("Done")
            self.done_pill.set_tone("ok")

    def import_another(self):
        session = self.controller.session
        session.summary = None
        session.report = None
        session.validated = False
        self.controller.go(2)


class MainWindow(QMainWindow):
    STEPS = [
        (1, "Connect"),
        (2, "Experiment"),
        (3, "Files"),
        (4, "Validate"),
        (5, "Review & import"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIMPLE")
        self.setMinimumSize(1000, 720)
        self.resize(1180, 820)

        self.settings = QSettings("SIMPLE", "simple-gui")
        self.session = Session(api_client=silex.ApiClient(verbose=False))
        self._busy = False
        self._threads = []
        self._disc_thread = None

        self._build()
        self._restore_settings()
        self.refresh()

    # ---- construction ------------------------------------------------------

    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.sidebar = Sidebar(self.STEPS)
        for index, row in enumerate(self.sidebar.rows):
            row.clicked.connect(lambda i=index: self.go(i))
        outer.addWidget(self.sidebar)

        main = QWidget()
        column = QVBoxLayout(main)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("topbar")
        topbar.setFixedHeight(62)
        top_row = QHBoxLayout(topbar)
        top_row.setContentsMargins(28, 0, 28, 0)
        top_row.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.top_title = label("No experiment")
        self.top_title.setStyleSheet("font-weight: 700; font-size: 15px;")
        self.top_sub = label("Not connected", "faint")
        titles.addWidget(self.top_title)
        titles.addWidget(self.top_sub)
        top_row.addLayout(titles, 1)
        top_row.setAlignment(titles, Qt.AlignmentFlag.AlignVCenter)
        self.top_pill = Pill("● Not connected", "idle")
        top_row.addWidget(self.top_pill, 0, Qt.AlignmentFlag.AlignVCenter)
        self.top_switch = QPushButton("Switch")
        self.top_switch.setObjectName("ghost")
        self.top_switch.clicked.connect(lambda: self.go(0))
        top_row.addWidget(self.top_switch)
        column.addWidget(topbar)

        self.stack = QStackedWidget()
        self.pages = [
            ConnectPage(self),
            ExperimentPage(self),
            FilesPage(self),
            ValidatePage(self),
            ImportPage(self),
        ]
        for page in self.pages:
            self.stack.addWidget(page)
        column.addWidget(self.stack, 1)

        statusbar = QFrame()
        statusbar.setObjectName("statusbar")
        statusbar.setFixedHeight(30)
        status_row = QHBoxLayout(statusbar)
        status_row.setContentsMargins(28, 0, 28, 0)
        status_row.addWidget(label("OpenSilex 1.5.2  ·  MIAPPE 1.2", "faint"))
        status_row.addStretch(1)
        status_row.addWidget(label(f"SIMPLE {__version__}", "faint"))
        column.addWidget(statusbar)

        outer.addWidget(main, 1)

    def _restore_settings(self):
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        host = self.settings.value("instance", "")
        remember = str(self.settings.value("remember", "false")).lower() in (
            "true",
            "1",
        )
        connect_page = self.pages[0]
        if host:
            for index in range(connect_page.instance.count()):
                name = connect_page.instance.itemText(index)
                if INSTANCES.get(host) == name:
                    connect_page.instance.setCurrentIndex(index)
                    break
        if remember:
            connect_page.remember.setChecked(True)
            user = self.settings.value("user", "")
            if user:
                connect_page.user.setText(user)

    # ---- state -------------------------------------------------------------

    def max_step(self):
        session = self.session
        if not session.connected:
            return 0
        if not session.folder:
            return 1
        limit = 2
        if session.miappe and session.tabular:
            limit = 3
        if session.validated:
            limit = 4
        return limit

    def refresh(self):
        session = self.session
        done = [
            session.connected,
            bool(session.folder),
            bool(session.miappe and session.tabular),
            session.validated,
            session.summary is not None,
        ]
        limit = self.max_step()
        enabled = [not self._busy and index <= limit for index in range(len(self.pages))]
        self.sidebar.set_states(self.stack.currentIndex(), done, enabled)
        self.sidebar.rows[0].set_caption(session.host_label or "not connected")
        if session.discovery is not None and session.discovery.experiment_name:
            self.sidebar.rows[1].set_caption(session.discovery.experiment_name)
        elif session.folder:
            self.sidebar.rows[1].set_caption(os.path.basename(session.folder.rstrip(os.sep)))
        else:
            self.sidebar.rows[1].set_caption("no folder selected")
        self.sidebar.rows[2].set_caption(
            "MIAPPE + tabular data"
            if session.miappe and session.tabular
            else "files not selected"
        )
        if session.report is not None:
            bits = [f"{session.report.passed} passed"]
            if session.report.warnings:
                bits.append(f"{session.report.warnings} warning(s)")
            if session.report.errors:
                bits.append(f"{session.report.errors} error(s)")
            self.sidebar.rows[3].set_caption(" · ".join(bits))
        else:
            self.sidebar.rows[3].set_caption("not run yet")
        if self.session_import_running():
            import_caption = "running…"
        elif session.summary is not None:
            import_caption = "finished"
        elif session.validated:
            import_caption = "ready"
        else:
            import_caption = "locked"
        self.sidebar.rows[4].set_caption(import_caption)

        experiment = (
            session.discovery.experiment_name
            if session.discovery is not None
            else None
        )
        self.top_title.setText(
            experiment
            or (os.path.basename(session.folder.rstrip(os.sep)) if session.folder else "No experiment")
        )
        if session.connected:
            self.top_sub.setText(session.host_label)
            self.top_pill.setText("● Connected")
            self.top_pill.set_tone("ok")
        else:
            self.top_sub.setText("Not connected")
            self.top_pill.setText("● Not connected")
            self.top_pill.set_tone("idle")
        self.top_switch.setEnabled(session.connected and not self._busy)

    def go(self, index):
        if self._busy or index < 0 or index >= len(self.pages):
            return
        if index > self.max_step():
            return
        self.stack.setCurrentIndex(index)
        self.pages[index].on_show()
        self.refresh()

    def set_busy(self, busy):
        self._busy = busy
        self.refresh()
        if busy:
            self.sidebar.set_states(self.stack.currentIndex(), self._done_flags(), [False] * len(self.pages))

    def _done_flags(self):
        session = self.session
        return [
            session.connected,
            bool(session.folder),
            bool(session.miappe and session.tabular),
            session.validated,
            session.summary is not None,
        ]

    # ---- file/session mutations -------------------------------------------

    def set_folder(self, folder):
        session = self.session
        session.folder = folder
        session.discovery = None
        session.miappe = None
        session.tabular = None
        session.datafiles = None
        self._invalidate(clear_summary=True)
        self.pages[1].refresh()
        self.pages[2].refresh()
        self.refresh()
        self.pages[1].status.setText("Reading folder…")

        thread = TaskThread(lambda: discovery.discover(folder), self)
        self._disc_thread = thread
        thread.done.connect(self._discovered)
        thread.error.connect(lambda message: self.pages[1].status.setText(message))
        thread.start()

    def _discovered(self, result):
        session = self.session
        session.discovery = result
        session.miappe = result.miappe
        session.tabular = result.tabular
        session.datafiles = result.datafiles
        self._invalidate()
        self.pages[1].refresh()
        self.pages[2].refresh()
        self.refresh()

    def set_miappe(self, path):
        self.session.miappe = path
        try:
            name = discovery.experiment_name(path)
        except Exception:
            name = None
        if name and self.session.discovery is not None:
            self.session.discovery.experiment_name = name
        self._invalidate()
        self.pages[1].refresh()
        self.pages[2].refresh()
        self.refresh()

    def set_tabular(self, path):
        self.session.tabular = path
        self._invalidate()
        self.pages[1].refresh()
        self.pages[2].refresh()
        self.refresh()

    def set_datafiles(self, path):
        self.session.datafiles = path
        self._invalidate()
        self.pages[1].refresh()
        self.pages[2].refresh()
        self.refresh()

    def _invalidate(self, clear_summary=True):
        session = self.session
        session.report = None
        session.validated = False
        if clear_summary:
            session.summary = None

    def append_log(self, level, message):
        self.session.log_entries.append((level, clean_rich(message)))
        if len(self.session.log_entries) > 5000:
            del self.session.log_entries[:1000]

    def view_log(self):
        LogDialog("SIMPLE import log", self.session.log_entries, self).exec()

    # ---- window ------------------------------------------------------------

    def closeEvent(self, event):
        if self.session_import_running():
            QMessageBox.warning(
                self,
                "Import running",
                "An import is still running. Cancel it or wait for it to finish "
                "before closing SIMPLE.",
            )
            event.ignore()
            return
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)

    def session_import_running(self):
        page = self.pages[4]
        return page.thread is not None and page.thread.isRunning()


def run():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(QSS)
    app.setApplicationName("SIMPLE")
    window = MainWindow()
    window.show()
    return app.exec()
