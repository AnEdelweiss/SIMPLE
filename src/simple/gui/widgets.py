"""Reusable widgets for the dashboard GUI."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from simple.gui.text import clean_rich
from simple.gui.theme import (
    AMBER,
    AMBER_BG,
    BORDER,
    FAINT,
    GREEN,
    GREEN_BG,
    MUTED,
    RED,
    RED_BG,
    TEXT,
)

LEVEL_COLORS = {
    "ok": GREEN,
    "info": MUTED,
    "warn": AMBER,
    "error": RED,
}


def label(text, name=None, wrap=False):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    lab.setWordWrap(wrap)
    return lab


def hline():
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {BORDER};")
    return line


class Card(QFrame):
    """A white rounded panel with a vertical body layout."""

    def __init__(self, padding=16, spacing=10, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(spacing)


class Pill(QLabel):
    def __init__(self, text="", tone="ok"):
        super().__init__(text)
        self.setFixedHeight(26)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_tone(tone)

    def set_tone(self, tone):
        colors = {
            "ok": (GREEN_BG, GREEN),
            "warn": (AMBER_BG, AMBER),
            "error": (RED_BG, RED),
            "idle": ("#eef0f3", MUTED),
        }
        background, foreground = colors.get(tone, colors["idle"])
        self.setStyleSheet(
            f"background: {background}; color: {foreground}; border-radius: 12px;"
            "padding: 5px 12px; font-weight: 700; font-size: 12px;"
        )


class StepRow(QWidget):
    """One sidebar entry: status bubble, title and caption."""

    clicked = pyqtSignal()

    def __init__(self, number, title, parent=None):
        super().__init__(parent)
        self.number = number
        self.state = "pending"
        self._enabled = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        box = QHBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(11)

        self.bubble = QLabel(str(number))
        self.bubble.setFixedSize(26, 26)
        self.bubble.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.bubble, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(1)
        self.title = label(title)
        self.caption = label("")
        self.caption.setStyleSheet(f"color: {FAINT}; font-size: 11px;")
        text.addWidget(self.title)
        text.addWidget(self.caption)
        box.addLayout(text, 1)

        self.set_state("pending", "")

    def set_state(self, state, caption=None):
        self.state = state
        if state == "done":
            self.bubble.setText("✓")
            self.bubble.setStyleSheet(
                f"background: {GREEN_BG}; color: {GREEN}; border-radius: 13px;"
                "font-weight: 700;"
            )
            self.title.setStyleSheet(f"font-weight: 700; color: {TEXT};")
        elif state == "active":
            self.bubble.setText(str(self.number))
            self.bubble.setStyleSheet(
                f"background: {GREEN}; color: white; border-radius: 13px;"
                "font-weight: 700;"
            )
            self.title.setStyleSheet(f"font-weight: 700; color: {TEXT};")
        else:
            self.bubble.setText(str(self.number))
            self.bubble.setStyleSheet(
                f"background: #eef0f3; color: {FAINT}; border-radius: 13px;"
                "font-weight: 700;"
            )
            self.title.setStyleSheet(f"font-weight: 700; color: {MUTED};")
        if caption is not None:
            self.caption.setText(caption)

    def set_caption(self, caption):
        self.caption.setText(caption)

    def set_enabled(self, enabled):
        self._enabled = enabled
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if enabled
            else Qt.CursorShape.ArrowCursor
        )

    def mousePressEvent(self, event):
        if self._enabled:
            self.clicked.emit()
        super().mousePressEvent(event)


class Sidebar(QFrame):
    def __init__(self, steps, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(248)
        self.rows = []

        box = QVBoxLayout(self)
        box.setContentsMargins(20, 22, 18, 18)
        box.setSpacing(0)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel("S")
        logo.setFixedSize(30, 30)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            f"background: {GREEN}; color: white; border-radius: 8px;"
            "font-weight: 700; font-size: 15px;"
        )
        brand.addWidget(logo)
        names = QVBoxLayout()
        names.setSpacing(0)
        name = label("SIMPLE")
        name.setStyleSheet("font-weight: 700; font-size: 15px;")
        names.addWidget(name)
        names.addWidget(label("Import data", "faint"))
        brand.addLayout(names, 1)
        box.addLayout(brand)
        box.addSpacing(26)

        for number, title in steps:
            row = StepRow(number, title)
            self.rows.append(row)
            box.addWidget(row)
            box.addSpacing(16)

        box.addStretch(1)
        box.addWidget(hline())
        box.addSpacing(12)
        docs = QPushButton("Documentation")
        docs.setObjectName("link")
        docs.setCursor(Qt.CursorShape.PointingHandCursor)
        docs.clicked.connect(self._open_docs)
        box.addWidget(docs)
        box.addSpacing(8)
        logs = QPushButton("Open log folder")
        logs.setObjectName("link")
        logs.setCursor(Qt.CursorShape.PointingHandCursor)
        logs.clicked.connect(self._open_logs)
        box.addWidget(logs)

    def _open_docs(self):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl("https://anedelweiss.github.io/SIMPLE/"))

    def _open_logs(self):
        import os
        import tempfile
        from pathlib import Path

        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        candidates = []
        env_dir = os.environ.get("SIMPLE_LOG_DIR")
        if env_dir:
            candidates.append(Path(env_dir))
        candidates.append(Path(__file__).resolve().parent.parent / "logs_SIMPLE")
        candidates.append(Path(tempfile.gettempdir()) / "simple_logs")
        for candidate in candidates:
            if candidate.is_dir():
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(candidate)))
                return
        QDesktopServices.openUrl(QUrl.fromLocalFile(os.getcwd()))

    def set_states(self, active, done, enabled):
        for index, row in enumerate(self.rows):
            if done[index]:
                state = "done"
            elif index == active:
                state = "active"
            else:
                state = "pending"
            row.set_state(state)
            row.set_enabled(enabled[index])


class FileRow(QWidget):
    change_requested = pyqtSignal()

    def __init__(self, name, value="", parent=None):
        super().__init__(parent)
        box = QHBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(14)

        self.name = label(name, "faint")
        self.name.setFixedWidth(110)
        box.addWidget(self.name, 0, Qt.AlignmentFlag.AlignTop)

        self.value = label(value, "mono", wrap=True)
        self.value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        box.addWidget(self.value, 1)

        self.button = QPushButton("Change")
        self.button.setObjectName("link")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self.change_requested)
        box.addWidget(self.button, 0, Qt.AlignmentFlag.AlignTop)

    def set_value(self, value):
        self.value.setText(value or "—")
        self.value.setToolTip(value or "")

    def set_change_visible(self, visible):
        self.button.setVisible(visible)


class CheckRow(QWidget):
    def __init__(self, text, level="ok", parent=None):
        super().__init__(parent)
        box = QHBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(9)

        glyph, background = {
            "ok": ("✓", GREEN_BG),
            "warn": ("⚠", AMBER_BG),
            "error": ("✗", RED_BG),
            "info": ("·", "#eef0f3"),
            "pending": ("○", "#eef0f3"),
            "active": ("●", GREEN_BG),
        }.get(level, ("·", "#eef0f3"))
        color = {
            "ok": GREEN,
            "warn": AMBER,
            "error": RED,
            "info": MUTED,
            "pending": FAINT,
            "active": GREEN,
        }.get(level, MUTED)

        badge = QLabel(glyph)
        badge.setFixedSize(18, 18)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background: {background}; color: {color}; border-radius: 9px;"
            "font-weight: 700;"
        )
        box.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)

        self.text = label(text, "muted", wrap=True)
        box.addWidget(self.text, 1)


class MetricTile(QFrame):
    def __init__(self, value, caption, parent=None):
        super().__init__(parent)
        self.setObjectName("tile")
        box = QVBoxLayout(self)
        box.setContentsMargins(12, 9, 12, 9)
        box.setSpacing(0)
        self.value = label(str(value), "metric")
        self.caption = label(caption, "metriclabel")
        box.addWidget(self.value)
        box.addWidget(self.caption)

    def set_value(self, value):
        self.value.setText(str(value))


class LogView(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("log")
        self.setReadOnly(True)
        self.setMaximumBlockCount(5000)

    def append_entry(self, level, message):
        color = LEVEL_COLORS.get(level, MUTED)
        html = (
            f'<span style="color:{color};">'
            f"{level.upper():<5}  {clean_rich(message)}</span>"
        )
        self.appendHtml(html)
        self.moveCursor(QTextCursor.MoveOperation.End)

    def append_entries(self, entries):
        for level, message in entries:
            self.append_entry(level, message)


class LogDialog(QDialog):
    def __init__(self, title, entries, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(820, 520)
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 16, 16, 16)
        box.setSpacing(10)

        view = LogView()
        view.append_entries(entries)
        box.addWidget(view, 1)

        row = QHBoxLayout()
        save = QPushButton("Save log…")
        save.setObjectName("ghost")
        save.clicked.connect(lambda: self._save(view))
        row.addWidget(save)
        row.addStretch(1)
        close = QPushButton("Close")
        close.setObjectName("ghost")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        box.addLayout(row)

    def _save(self, view):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save log", "simple.log", "Log files (*.log *.txt)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(view.toPlainText())
