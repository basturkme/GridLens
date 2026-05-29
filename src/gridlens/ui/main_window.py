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
from gridlens.core.models import Network, SolutionResult
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

        self._network: Network | None = None

        # ----- Wiring -----
        self._sidebar.pageChanged.connect(self._switch_page)
        network_view = self._pages["network"]
        if hasattr(network_view, "busPicked"):
            network_view.busPicked.connect(self._on_bus_picked)
        self._switch_page("home")

    def set_network(
        self, network: Network | None, solution: SolutionResult | None = None
    ) -> None:
        """Load a network into the views that consume it."""
        self._network = network
        self._pages["network"].set_network(network, solution)
        if network is None:
            self.statusBar().showMessage("Idle")
            return
        msg = f"Loaded: {network.name or 'Untitled'} — {len(network.buses)} buses"
        if solution is not None:
            violations = sum(
                1 for b in solution.bus_results if b.violation != "ok"
            )
            msg += (
                f" · solved in {solution.iterations} iters"
                f" · {violations} voltage violation(s)"
                if solution.converged
                else " · solver did not converge"
            )
        self.statusBar().showMessage(msg)

    def _on_bus_picked(self, bus_id: str) -> None:
        self.statusBar().showMessage(f"Selected bus: {bus_id}")

    def _switch_page(self, key: str) -> None:
        page = self._pages.get(key)
        if page is None:
            return
        self._stack.setCurrentWidget(page)
        self._sidebar.select(key)
