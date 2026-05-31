from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gridlens.core.models import Network, SolutionResult
from gridlens.ui.views._base import PageView
from gridlens.ui.widgets.numeric_field import NumericField
from gridlens.utils.constants import DEFAULT_MAX_ITER, DEFAULT_TOLERANCE_PU


class SolverView(PageView):
    page_key = "solver"
    page_title = "Solver"
    breadcrumbs = ["Projects", "Solver"]

    # Emitted when the user requests a solve with (tolerance, max_iter).
    solveRequested = pyqtSignal(float, int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._network: Network | None = None
        self._tol = DEFAULT_TOLERANCE_PU

        body = QWidget()
        layout = QVBoxLayout(body)

        actions = QHBoxLayout()
        self._run_btn = QPushButton("Run Power Flow")
        self._run_btn.setObjectName("PrimaryButton")
        self._run_btn.clicked.connect(self._emit_solve)
        self._run_btn.setEnabled(False)
        actions.addWidget(self._run_btn)

        settings = QFormLayout()
        self._tol_field = NumericField(minimum=1e-12)
        self._tol_field.setText(f"{DEFAULT_TOLERANCE_PU:g}")
        self._tol_field.valueChanged.connect(self._on_tol_changed)
        settings.addRow("Tolerance (pu)", self._tol_field)

        self._iter_spin = QSpinBox()
        self._iter_spin.setRange(1, 1000)
        self._iter_spin.setValue(DEFAULT_MAX_ITER)
        settings.addRow("Max iterations", self._iter_spin)

        actions.addLayout(settings)
        actions.addStretch(1)
        layout.addLayout(actions)

        layout.addSpacing(8)
        layout.addWidget(QLabel("Convergence log"))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText(
            "Solver output appears here once a network is loaded and 'Run' is pressed."
        )
        layout.addWidget(self._log, 1)

        self.set_content(body)

    # -- public API --------------------------------------------------------- #
    def set_network(
        self, network: Network | None, solution: SolutionResult | None = None
    ) -> None:
        self._network = network
        self._run_btn.setEnabled(network is not None)
        if network is None:
            self._log.clear()
        elif solution is not None:
            self.show_result(solution)

    def show_result(self, result: SolutionResult) -> None:
        self._log.setPlainText(self._format(result))

    # -- internals ---------------------------------------------------------- #
    def _on_tol_changed(self, value: float) -> None:
        self._tol = value

    def _emit_solve(self) -> None:
        self.solveRequested.emit(self._tol, self._iter_spin.value())

    def _format(self, result: SolutionResult) -> str:
        lines = [
            "Power flow result",
            f"  Status:        {'Converged' if result.converged else 'NOT converged'}",
            f"  Iterations:    {result.iterations}",
            f"  Max mismatch:  {result.max_mismatch:.3e} pu",
            f"  Message:       {result.message}",
        ]
        if result.bus_results:
            violations = [b for b in result.bus_results if b.violation != "ok"]
            lines.append(
                f"  Buses:         {len(result.bus_results)}"
                f"  ({len(violations)} violation(s))"
            )
            worst = min(result.bus_results, key=lambda b: b.v_pu)
            lines.append(
                f"  Lowest |V|:    {worst.v_pu:.4f} pu at {worst.bus_id}"
            )
            for b in violations:
                lines.append(
                    f"    - {b.bus_id}: {b.v_pu:.4f} pu  ({b.violation}voltage)"
                )
        return "\n".join(lines)
