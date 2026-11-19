"""Identidade visual: tema escuro técnico."""

BG = "#10141C"
PANEL = "#181F2B"
PANEL2 = "#222C3A"
BLUE = "#2389FF"
CYAN = "#19C7D9"
TEXT = "#E8EDF5"
TEXT2 = "#94A3B8"
WARN = "#F5A623"
ERR = "#FF5C6C"
OK = "#3DD68C"

STYLESHEET = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-family: 'Segoe UI', sans-serif; font-size: 13px; }}
QMainWindow::separator {{ background: {PANEL2}; width: 2px; height: 2px; }}
QMenuBar {{ background: {PANEL}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: {BLUE}; }}
QMenu {{ background: {PANEL}; border: 1px solid {PANEL2}; }}
QMenu::item:disabled {{ color: {TEXT2}; }}
QDockWidget {{ titlebar-close-icon: none; font-weight: 600; }}
QDockWidget::title {{ background: {PANEL2}; padding: 6px; color: {CYAN}; }}
QTreeWidget, QPlainTextEdit, QLineEdit, QTextEdit, QListWidget {{
    background: {PANEL}; border: 1px solid {PANEL2}; selection-background-color: {BLUE}; }}
QPushButton {{ background: {PANEL2}; border: 1px solid {BLUE}; padding: 6px 14px; border-radius: 3px; }}
QPushButton:hover {{ background: {BLUE}; }}
QPushButton:disabled {{ border-color: {PANEL2}; color: {TEXT2}; }}
QTabWidget::pane {{ border: 1px solid {PANEL2}; }}
QTabBar::tab {{ background: {PANEL}; padding: 6px 14px; }}
QTabBar::tab:selected {{ background: {PANEL2}; color: {CYAN}; }}
QStatusBar {{ background: {PANEL}; color: {TEXT2}; }}
QLabel#title {{ font-size: 26px; font-weight: 700; color: {TEXT}; }}
QLabel#subtitle {{ color: {TEXT2}; }}
QLabel#planned {{ color: {WARN}; }}
"""
