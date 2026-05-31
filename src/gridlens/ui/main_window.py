from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from gridlens import __app_name__
from gridlens._resources import default_example
from gridlens.core import load_network, save_network, solve
from gridlens.core.models import Network, SolutionResult
from gridlens.core.parser import ParserError
from gridlens.utils.constants import DEFAULT_MAX_ITER, DEFAULT_TOLERANCE_PU
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

_FILE_FILTER = "GridLens network (*.json);;All files (*)"


class MainWindow(QMainWindow):
    """Top-level shell — header + sidebar + central stack + footer."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
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
        self._solution: SolutionResult | None = None
        self._current_path: Path | None = None
        self._dirty = False
        self._tol = DEFAULT_TOLERANCE_PU
        self._max_iter = DEFAULT_MAX_ITER

        self._build_menu()

        # ----- Wiring -----
        self._sidebar.pageChanged.connect(self._switch_page)
        network_view = self._pages["network"]
        if hasattr(network_view, "busPicked"):
            network_view.busPicked.connect(self._on_bus_picked)
        if hasattr(network_view, "itemPicked"):
            network_view.itemPicked.connect(self._on_item_picked)
        equipment_view = self._pages["equipment"]
        if hasattr(equipment_view, "networkEdited"):
            equipment_view.networkEdited.connect(self._on_network_edited)
        home_view = self._pages["home"]
        if hasattr(home_view, "openRequested"):
            home_view.openRequested.connect(self._action_open)
            home_view.reloadExampleRequested.connect(self._action_reload_example)
        solver_view = self._pages["solver"]
        if hasattr(solver_view, "solveRequested"):
            solver_view.solveRequested.connect(self._on_solve_requested)

        self._switch_page("home")
        self._update_title()

    # ----------------------------------------------------------------- #
    # Menu
    # ----------------------------------------------------------------- #
    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")

        def add(text: str, slot, key: QKeySequence.StandardKey | None = None) -> None:
            action = QAction(text, self)
            if key is not None:
                action.setShortcut(key)
            action.triggered.connect(slot)
            file_menu.addAction(action)

        add("&New", self._action_new, QKeySequence.StandardKey.New)
        add("&Open…", self._action_open, QKeySequence.StandardKey.Open)
        file_menu.addSeparator()
        add("&Save", self._action_save, QKeySequence.StandardKey.Save)
        add("Save &As…", self._action_save_as, QKeySequence.StandardKey.SaveAs)
        file_menu.addSeparator()
        add("Reload &Example", self._action_reload_example)
        file_menu.addSeparator()
        add("E&xit", self.close, QKeySequence.StandardKey.Quit)

    # ----------------------------------------------------------------- #
    # Core file operations (dialog-free — directly unit-testable)
    # ----------------------------------------------------------------- #
    def open_path(self, path: str | Path, *, set_current: bool = True) -> None:
        """Load + validate + solve a network from disk and display it.

        Raises ParserError if the file is malformed; the current network is left
        untouched in that case. With ``set_current=False`` the file does not
        become the save target — used for the bundled example so a stray Ctrl+S
        cannot overwrite the shipped reference; the user must Save As instead.
        """
        network = load_network(path)  # raises ParserError before any UI change
        self.set_network(network, solve(network))
        self._current_path = Path(path) if set_current else None
        self._set_dirty(False)

    def save_to(self, path: str | Path) -> None:
        """Serialize the current network to disk and mark it clean."""
        if self._network is None:
            return
        save_network(self._network, path)
        self._current_path = Path(path)
        self._set_dirty(False)

    def new_network(self) -> None:
        """Clear the workspace to an empty state."""
        self.set_network(None)
        self._current_path = None
        self._set_dirty(False)

    def load_startup_example(self) -> bool:
        """Best-effort open of the bundled example so the app opens populated.
        Returns True if a network was loaded."""
        path = default_example()
        if path is None:
            return False
        try:
            self.open_path(path, set_current=False)
            return True
        except (ParserError, OSError):
            return False

    # ----------------------------------------------------------------- #
    # Menu/dialog action handlers
    # ----------------------------------------------------------------- #
    def _action_new(self) -> None:
        if not self._confirm_discard():
            return
        self.new_network()

    def _action_open(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open network file", self._dialog_dir(), _FILE_FILTER
        )
        if not path:
            return
        try:
            self.open_path(path)
        except (ParserError, OSError) as exc:
            QMessageBox.critical(self, "Could not open file", str(exc))

    def _action_save(self) -> bool:
        if self._network is None:
            return False
        if self._current_path is None:
            return self._action_save_as()
        try:
            self.save_to(self._current_path)
            return True
        except OSError as exc:
            QMessageBox.critical(self, "Could not save file", str(exc))
            return False

    def _action_save_as(self) -> bool:
        if self._network is None:
            return False
        path, _ = QFileDialog.getSaveFileName(
            self, "Save network as", self._dialog_dir(), _FILE_FILTER
        )
        if not path:
            return False
        try:
            self.save_to(path)
            return True
        except OSError as exc:
            QMessageBox.critical(self, "Could not save file", str(exc))
            return False

    def _action_reload_example(self) -> None:
        if not self._confirm_discard():
            return
        path = default_example()
        if path is None:
            QMessageBox.information(
                self, "No example available", "The bundled example was not found."
            )
            return
        try:
            self.open_path(path, set_current=False)
        except (ParserError, OSError) as exc:
            QMessageBox.critical(self, "Could not open example", str(exc))

    # ----------------------------------------------------------------- #
    # Network display + live re-solve
    # ----------------------------------------------------------------- #
    def set_network(
        self, network: Network | None, solution: SolutionResult | None = None
    ) -> None:
        """Load a network into the views that consume it."""
        self._network = network
        self._solution = solution
        for key in ("network", "equipment", "solver", "reports"):
            self._pages[key].set_network(network, solution)
        self.statusBar().showMessage(self._status_text())

    def _on_network_edited(self) -> None:
        """An equipment value changed — re-solve and refresh the views live."""
        if self._network is None:
            return
        self._solution = solve(self._network, tol=self._tol, max_iter=self._max_iter)
        self._refresh_solution_views(preserve_equipment_focus=True)
        self._set_dirty(True)
        self.statusBar().showMessage(self._status_text())

    def _on_solve_requested(self, tol: float, max_iter: int) -> None:
        """The Solver page asked to re-run with explicit tolerance / iterations."""
        if self._network is None:
            return
        self._tol = tol
        self._max_iter = max_iter
        self._solution = solve(self._network, tol=tol, max_iter=max_iter)
        self._refresh_solution_views(preserve_equipment_focus=False)
        self.statusBar().showMessage(self._status_text())

    def _refresh_solution_views(self, *, preserve_equipment_focus: bool) -> None:
        """Push the current solution to every view. The equipment editor is
        refreshed via apply_solution (which keeps the open form/focus) while a
        full edit is in progress; otherwise it is rebuilt like the rest."""
        self._pages["network"].set_network(self._network, self._solution)
        self._pages["solver"].set_network(self._network, self._solution)
        self._pages["reports"].set_network(self._network, self._solution)
        if preserve_equipment_focus:
            self._pages["equipment"].apply_solution(self._solution)
        else:
            self._pages["equipment"].set_network(self._network, self._solution)

    def _status_text(self) -> str:
        if self._network is None:
            return "Idle"
        msg = (
            f"Loaded: {self._network.name or 'Untitled'} — "
            f"{len(self._network.buses)} buses"
        )
        sol = self._solution
        if sol is not None:
            if sol.converged:
                violations = sum(1 for b in sol.bus_results if b.violation != "ok")
                msg += (
                    f" · solved in {sol.iterations} iters"
                    f" · {violations} voltage violation(s)"
                )
            else:
                msg += " · solver did not converge"
        return msg

    def _on_bus_picked(self, bus_id: str) -> None:
        """Clicking a bus on the diagram jumps to its editor on the Equipment page."""
        equipment = self._pages["equipment"]
        if self._network is not None and hasattr(equipment, "edit_bus"):
            self._switch_page("equipment")
            equipment.edit_bus(bus_id)
            self.statusBar().showMessage(f"Editing bus: {bus_id}")
        else:
            self.statusBar().showMessage(f"Selected bus: {bus_id}")

    def _on_item_picked(self, kind: str, obj_id: str) -> None:
        """Clicking a load / generator / capacitor symbol jumps to its editor."""
        equipment = self._pages["equipment"]
        if self._network is not None and hasattr(equipment, "edit_item"):
            self._switch_page("equipment")
            equipment.edit_item(kind, obj_id)
            self.statusBar().showMessage(f"Editing {kind}: {obj_id}")

    def _switch_page(self, key: str) -> None:
        page = self._pages.get(key)
        if page is None:
            return
        self._stack.setCurrentWidget(page)
        self._sidebar.select(key)

    # ----------------------------------------------------------------- #
    # Dirty state / title / discard guard
    # ----------------------------------------------------------------- #
    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self.setWindowModified(dirty)
        self._update_title()

    def _update_title(self) -> None:
        if self._current_path is not None:
            name = self._current_path.name
        elif self._network is not None:
            name = self._network.name or "Untitled"
        else:
            name = "No file"
        # The [*] placeholder is shown only while setWindowModified(True).
        self.setWindowTitle(f"{__app_name__} — {name}[*] — Distribution Feeder Analyzer")

    def _dialog_dir(self) -> str:
        if self._current_path is not None:
            return str(self._current_path.parent)
        example = default_example()
        return str(example.parent) if example is not None else ""

    def _confirm_discard(self) -> bool:
        """Returns True if it's safe to proceed (discard or saved), False if the
        user cancelled."""
        if not self._dirty or self._network is None:
            return True
        choice = QMessageBox.warning(
            self,
            "Unsaved changes",
            "The current network has unsaved changes. Save them first?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
        )
        if choice == QMessageBox.StandardButton.Save:
            return self._action_save()
        if choice == QMessageBox.StandardButton.Discard:
            return True
        return False

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
