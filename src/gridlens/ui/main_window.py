from __future__ import annotations

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from gridlens import __app_name__
from gridlens.ui.shell.footer import Footer
from gridlens.ui.shell.header_bar import HeaderBar
from gridlens.ui.shell.sidebar import Sidebar
from gridlens.ui.views import (
    AboutView,
    EquipmentView,
    HomeView,
    NetworkView,
    ReportsView,
    SettingsView,
    SolverView,
)


class MainWindow(QMainWindow):
    """Top-level shell — header + sidebar + central stack + footer."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{__app_name__} — Distribution Feeder Analyzer")
        self.resize(1280, 800)

        # ----- Central layout -----
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header = HeaderBar()
        outer.addWidget(self._header)

        body_row = QHBoxLayout()
        body_row.setContentsMargins(0, 0, 0, 0)
        body_row.setSpacing(0)

        self._sidebar = Sidebar()
        body_row.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        self._pages: dict[str, QWidget] = {}
        for view_cls in (
            HomeView,
            NetworkView,
            SolverView,
            EquipmentView,
            ReportsView,
            SettingsView,
            AboutView,
        ):
            view = view_cls()
            self._stack.addWidget(view)
            self._pages[view.page_key] = view
        body_row.addWidget(self._stack, 1)

        outer.addLayout(body_row, 1)

        self._footer = Footer()
        outer.addWidget(self._footer)

        self.setCentralWidget(central)

        # ----- Status bar -----
        status = QStatusBar()
        status.showMessage("Idle")
        self.setStatusBar(status)

        # ----- Wiring -----
        self._sidebar.pageChanged.connect(self._switch_page)
        self._switch_page("home")

    def _switch_page(self, key: str) -> None:
        page = self._pages.get(key)
        if page is None:
            return
        self._stack.setCurrentWidget(page)
        self._sidebar.select(key)
