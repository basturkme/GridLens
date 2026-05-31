from __future__ import annotations

import csv
from pathlib import Path

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gridlens.core.models import Network, SolutionResult
from gridlens.ui.theme.colors import Colors
from gridlens.ui.views._base import PageView
from gridlens.utils.constants import V_MAX_PU, V_MIN_PU

_VIOLATION_LABEL = {"ok": "OK", "under": "Undervoltage", "over": "Overvoltage"}
_VIOLATION_COLOR = {"ok": Colors.OK, "under": Colors.UNDER, "over": Colors.OVER}


class ReportsView(PageView):
    page_key = "reports"
    page_title = "Reports"
    breadcrumbs = ["Projects", "Reports"]

    HEADERS = ["Bus", "|V| (pu)", "∠V (°)", "|V| (kV)", "Status"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._network: Network | None = None
        self._solution: SolutionResult | None = None

        body = QWidget()
        layout = QVBoxLayout(body)

        toolbar = QHBoxLayout()
        self._export_btn = QPushButton("Export CSV")
        self._export_btn.setObjectName("SecondaryButton")
        self._export_btn.clicked.connect(self._on_export)
        self._export_btn.setEnabled(False)
        toolbar.addStretch(1)
        toolbar.addWidget(self._export_btn)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self._figure = Figure(figsize=(5, 2.6), tight_layout=True)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._ax = self._figure.add_subplot(111)
        splitter.addWidget(self._canvas)

        self._table = QTableWidget(0, len(self.HEADERS))
        self._table.setHorizontalHeaderLabels(self.HEADERS)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        splitter.addWidget(self._table)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.set_content(body)
        self._draw_chart()

    # -- public API --------------------------------------------------------- #
    def set_network(
        self, network: Network | None, solution: SolutionResult | None = None
    ) -> None:
        self._network = network
        self._solution = solution
        self._export_btn.setEnabled(solution is not None)
        self._fill_table()
        self._draw_chart()

    def export_csv(self, path: str | Path) -> None:
        """Write the current results table to a CSV file."""
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(self.HEADERS)
            writer.writerows(self._rows())

    # -- data --------------------------------------------------------------- #
    def _base_kv(self) -> dict[str, float]:
        if self._network is None:
            return {}
        return {b.id: b.base_kv for b in self._network.buses}

    def _rows(self) -> list[list[str]]:
        if self._solution is None:
            return []
        base_kv = self._base_kv()
        rows: list[list[str]] = []
        for b in self._solution.bus_results:
            kv = b.v_pu * base_kv.get(b.bus_id, 0.0)
            rows.append(
                [
                    b.bus_id,
                    f"{b.v_pu:.4f}",
                    f"{b.angle_deg:+.3f}",
                    f"{kv:.3f}",
                    _VIOLATION_LABEL.get(b.violation, b.violation),
                ]
            )
        return rows

    # -- table -------------------------------------------------------------- #
    def _fill_table(self) -> None:
        results = self._solution.bus_results if self._solution else []
        rows = self._rows()
        self._table.setRowCount(len(results))
        for r, bus in enumerate(results):
            tint = QColor(_VIOLATION_COLOR.get(bus.violation, Colors.TEXT))
            for c, text in enumerate(rows[r]):
                item = QTableWidgetItem(text)
                if bus.violation != "ok":
                    item.setForeground(QBrush(tint))
                self._table.setItem(r, c, item)

    # -- chart -------------------------------------------------------------- #
    def _draw_chart(self) -> None:
        ax = self._ax
        ax.clear()
        
        # Premium dark mode chart styling
        self._figure.set_facecolor(Colors.BG)
        ax.set_facecolor(Colors.BG_PANEL)
        ax.spines["bottom"].set_color(Colors.BORDER)
        ax.spines["left"].set_color(Colors.BORDER)
        ax.spines["top"].set_color("none")
        ax.spines["right"].set_color("none")
        ax.tick_params(colors=Colors.TEXT_MUTED, which="both", labelsize=8)
        ax.xaxis.label.set_color(Colors.TEXT)
        ax.yaxis.label.set_color(Colors.TEXT)
        ax.title.set_color(Colors.TEXT)
        
        results = self._solution.bus_results if self._solution else []
        if results:
            xs = list(range(len(results)))
            ys = [b.v_pu for b in results]
            labels = [b.bus_id for b in results]
            ax.plot(xs, ys, "-", color=Colors.BRAND, linewidth=1.5, zorder=1)
            ax.scatter(
                xs,
                ys,
                c=[_VIOLATION_COLOR.get(b.violation, Colors.OK) for b in results],
                zorder=2,
                s=40,
            )
            ax.axhline(V_MIN_PU, color=Colors.UNDER, linestyle="--", linewidth=0.8)
            ax.axhline(V_MAX_PU, color=Colors.OVER, linestyle="--", linewidth=0.8)
            ax.set_xticks(xs)
            ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
            ax.set_ylabel("|V| (pu)", fontsize=9)
            ax.set_title("Voltage profile", fontsize=10)
            ax.margins(x=0.05)
        else:
            ax.text(
                0.5, 0.5, "No solution to plot",
                ha="center", va="center", transform=ax.transAxes,
                color=Colors.TEXT_MUTED,
            )
            ax.set_xticks([])
            ax.set_yticks([])
        self._canvas.draw_idle()

    # -- export handler ----------------------------------------------------- #
    def _on_export(self) -> None:
        if self._solution is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export results as CSV", "voltages.csv", "CSV files (*.csv)"
        )
        if path:
            self.export_csv(path)
