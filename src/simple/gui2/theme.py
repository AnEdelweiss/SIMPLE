"""Visual constants and stylesheet for the experimental dashboard GUI."""

GREEN = "#2e7d4f"
GREEN_DARK = "#256b43"
GREEN_BG = "#e8f3ec"
AMBER = "#b45309"
AMBER_BG = "#fef5e7"
RED = "#b91c1c"
RED_BG = "#fdeaea"
TEXT = "#111827"
MUTED = "#6b7280"
FAINT = "#9ca3af"
BORDER = "#e5e7eb"
BG = "#f5f6f8"
CARD = "#ffffff"
SIDEBAR = "#ffffff"
LOG_BG = "#1e2421"
LOG_TEXT = "#d8e6dc"

QSS = f"""
* {{
    font-family: "Adwaita Sans", "Noto Sans", "Segoe UI", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QWidget#root {{ background: {BG}; }}
QFrame#sidebar {{ background: {SIDEBAR}; border-right: 1px solid {BORDER}; }}
QFrame#topbar {{ background: {CARD}; border-bottom: 1px solid {BORDER}; }}
QFrame#statusbar {{ background: {CARD}; border-top: 1px solid {BORDER}; }}
QFrame#card {{ background: {CARD}; border: 1px solid {BORDER}; border-radius: 10px; }}
QFrame#tile {{ background: #fafbfc; border: 1px solid {BORDER}; border-radius: 8px; }}
QLabel#title {{ font-size: 21px; font-weight: 700; }}
QLabel#subtitle {{ color: {MUTED}; font-size: 13px; }}
QLabel#cardtitle {{ font-size: 11px; font-weight: 700; color: {MUTED}; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#faint {{ color: {FAINT}; font-size: 12px; }}
QLabel#mono {{ font-family: "JetBrains Mono", monospace; font-size: 12px; }}
QLabel#metric {{ font-size: 22px; font-weight: 700; color: {GREEN}; }}
QLabel#metriclabel {{ font-size: 11px; color: {MUTED}; }}
QPushButton#primary {{
    background: {GREEN}; color: white; border: none; border-radius: 8px;
    padding: 10px 22px; font-weight: 600; font-size: 13px;
}}
QPushButton#primary:hover {{ background: {GREEN_DARK}; }}
QPushButton#primary:disabled {{ background: #cfd8d2; color: #f3f4f6; }}
QPushButton#ghost {{
    background: #ffffff; border: 1px solid #d1d5db; border-radius: 8px;
    padding: 9px 16px; color: #374151;
}}
QPushButton#ghost:hover {{ background: #f9fafb; }}
QPushButton#ghost:disabled {{ color: #c4c8cd; border-color: #e5e7eb; }}
QPushButton#danger {{
    background: #ffffff; border: 1px solid #fca5a5; border-radius: 8px;
    padding: 9px 16px; color: {RED}; font-weight: 600;
}}
QPushButton#danger:hover {{ background: #fff5f5; }}
QPushButton#link {{
    background: transparent; border: none; color: {GREEN};
    padding: 0; font-size: 12px; font-weight: 600;
}}
QPushButton#link:hover {{ color: {GREEN_DARK}; }}
QLineEdit, QComboBox {{
    background: #ffffff; border: 1px solid #d1d5db; border-radius: 7px;
    padding: 8px 10px; selection-background-color: {GREEN};
}}
QLineEdit:focus, QComboBox:focus {{ border: 1px solid {GREEN}; }}
QLineEdit:disabled, QComboBox:disabled {{ background: #f9fafb; color: {FAINT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    border: 1px solid {BORDER}; border-radius: 6px; background: white;
    selection-background-color: {GREEN_BG}; selection-color: {TEXT};
}}
QCheckBox {{ color: #374151; spacing: 8px; background: transparent; }}
QCheckBox::indicator {{
    width: 15px; height: 15px; border: 1px solid #cfd4da;
    border-radius: 4px; background: #ffffff;
}}
QCheckBox::indicator:checked {{
    background: {GREEN}; border: 1px solid {GREEN};
}}
QProgressBar {{
    border: none; border-radius: 5px; background: #edf0f2; height: 10px;
}}
QProgressBar::chunk {{ background: {GREEN}; border-radius: 5px; }}
QPlainTextEdit#log {{
    background: {LOG_BG}; color: {LOG_TEXT}; border: none; border-radius: 8px;
    font-family: "JetBrains Mono", monospace; font-size: 12px; padding: 10px;
}}
QDialog {{ background: {BG}; }}
QScrollArea {{ border: none; background: transparent; }}
QToolTip {{
    background: {TEXT}; color: #ffffff; border: none; padding: 5px 8px;
    border-radius: 4px;
}}
"""
