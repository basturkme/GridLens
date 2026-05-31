from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gridlens.core.models import Network, SolutionResult
from gridlens.ui.theme.colors import Colors
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
        self._run_counter = 0

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ----------------- Left Column (Controls & Flowchart) -----------------
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 12, 0)
        left_layout.setSpacing(16)

        # Settings group
        settings_box = QFrame()
        settings_box.setObjectName("settings_box")
        settings_box.setStyleSheet(f"""
            #settings_box {{
                background-color: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 12px;
            }}
        """)
        settings_layout = QVBoxLayout(settings_box)
        settings_layout.setSpacing(10)

        title_label = QLabel("Solver Configuration")
        title_label.setStyleSheet("font-weight: bold; font-size: 11pt; border: none;")
        settings_layout.addWidget(title_label)

        form = QFormLayout()
        form.setSpacing(8)
        self._tol_field = NumericField(minimum=1e-12)
        self._tol_field.setText(f"{DEFAULT_TOLERANCE_PU:g}")
        self._tol_field.valueChanged.connect(self._on_tol_changed)
        form.addRow("Tolerance (pu)", self._tol_field)

        self._iter_spin = QSpinBox()
        self._iter_spin.setRange(1, 1000)
        self._iter_spin.setValue(DEFAULT_MAX_ITER)
        self._iter_spin.setStyleSheet(f"QSpinBox {{ background-color: {Colors.BG}; border: 1px solid {Colors.BORDER}; color: {Colors.TEXT}; padding: 4px; border-radius: 4px; }}")
        form.addRow("Max iterations", self._iter_spin)
        settings_layout.addLayout(form)

        self._run_btn = QPushButton("Run Power Flow")
        self._run_btn.setObjectName("PrimaryButton")
        self._run_btn.clicked.connect(self._emit_solve)
        self._run_btn.setEnabled(False)
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_layout.addWidget(self._run_btn)

        left_layout.addWidget(settings_box)

        # Algorithm Flowchart Panel
        flow_box = QFrame()
        flow_box.setObjectName("flow_box")
        flow_box.setStyleSheet(f"""
            #flow_box {{
                background-color: {Colors.BG_PANEL};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
                padding: 16px;
            }}
        """)
        flow_layout = QVBoxLayout(flow_box)
        flow_layout.setSpacing(6)
        flow_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        flow_title = QLabel("Backward-Forward Sweep Flow")
        flow_title.setStyleSheet("font-weight: bold; font-size: 11pt; border: none; margin-bottom: 6px;")
        flow_layout.addWidget(flow_title)

        def make_step(step_num: str, text: str, desc: str) -> QFrame:
            frame = QFrame()
            frame.setObjectName("step_frame")
            frame.setStyleSheet(f"""
                #step_frame {{
                    background-color: {Colors.BG};
                    border: 1px solid {Colors.BORDER};
                    border-radius: 4px;
                    padding: 8px;
                }}
            """)
            fl = QVBoxLayout(frame)
            fl.setContentsMargins(8, 4, 8, 4)
            fl.setSpacing(2)
            lbl = QLabel(f"{step_num}. {text}")
            lbl.setStyleSheet(f"font-weight: bold; color: {Colors.BRAND}; border: none;")
            sub = QLabel(desc)
            sub.setStyleSheet(f"font-size: 8pt; color: {Colors.TEXT_MUTED}; border: none;")
            fl.addWidget(lbl)
            fl.addWidget(sub)
            return frame

        def make_arrow(text: str = "↓") -> QLabel:
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"font-weight: bold; color: {Colors.TEXT_MUTED}; border: none; font-size: 10pt;")
            return lbl

        flow_layout.addWidget(make_step("1", "Initialize Voltages", "Set initial bus voltages V_i = 1.0 pu"))
        flow_layout.addWidget(make_arrow())
        flow_layout.addWidget(make_step("2", "Backward Sweep", "Calculate branch currents from leaves to root"))
        flow_layout.addWidget(make_arrow())
        flow_layout.addWidget(make_step("3", "Forward Sweep", "Update bus voltage values from root to leaves"))
        flow_layout.addWidget(make_arrow())
        
        check_step = QFrame()
        check_step.setObjectName("check_step")
        check_step.setStyleSheet(f"""
            #check_step {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        cfl = QVBoxLayout(check_step)
        cfl.setContentsMargins(8, 4, 8, 4)
        cfl.setSpacing(2)
        clbl = QLabel("4. Convergence Check")
        clbl.setStyleSheet(f"font-weight: bold; color: {Colors.BRAND}; border: none;")
        csub = QLabel("Is Max |ΔV_i| < Tolerance?")
        csub.setStyleSheet(f"font-size: 8pt; color: {Colors.TEXT_MUTED}; border: none;")
        cfl.addWidget(clbl)
        cfl.addWidget(csub)
        flow_layout.addWidget(check_step)
        
        loop_arrow = QLabel("↺ Loop back to Step 2 if mismatch > tolerance")
        loop_arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loop_arrow.setStyleSheet(f"font-size: 8pt; font-style: italic; color: {Colors.TEXT_MUTED}; border: none; margin-top: 4px;")
        flow_layout.addWidget(loop_arrow)

        left_layout.addWidget(flow_box, 1)
        splitter.addWidget(left_pane)

        # ---------------- Right Column (Log & Mismatch Table) ----------------
        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(12, 0, 0, 0)
        right_layout.setSpacing(12)

        right_layout.addWidget(QLabel("Convergence log"))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText(
            "Solver output appears here once a network is loaded and 'Run' is pressed."
        )
        self._log.setMaximumHeight(160)
        right_layout.addWidget(self._log)

        right_layout.addWidget(QLabel("Iteration steps & mismatch history"))
        
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Iteration", "Max Mismatch (pu)", "Tolerance (pu)", "Status"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {Colors.BG};
                gridline-color: {Colors.BORDER};
                border: 1px solid {Colors.BORDER};
                border-radius: 6px;
            }}
        """)
        right_layout.addWidget(self._table, 1)

        splitter.addWidget(right_pane)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)
        self.set_content(body)

    # -- public API --------------------------------------------------------- #
    def set_network(
        self, network: Network | None, solution: SolutionResult | None = None
    ) -> None:
        self._network = network
        self._run_btn.setEnabled(network is not None)
        if network is None:
            self._log.clear()
            self._table.setRowCount(0)
            self._run_counter = 0
        else:
            self._log.clear()
            self._table.setRowCount(0)
            self._run_counter = 0
            if solution is not None:
                self.show_result(solution)

    def show_result(self, result: SolutionResult) -> None:
        formatted = self._format(result)
        if self._run_counter == 0:
            self._log.setPlainText(formatted)
        else:
            self._log.append("\n" + "—" * 45 + "\n\n" + formatted)
        self._populate_table(result)

    # -- internals ---------------------------------------------------------- #
    def _on_tol_changed(self, value: float) -> None:
        self._tol = value

    def _emit_solve(self) -> None:
        self.solveRequested.emit(self._tol, self._iter_spin.value())

    def _populate_table(self, result: SolutionResult) -> None:
        history = getattr(result, "mismatch_history", [])
        if not history:
            return
            
        self._run_counter += 1
        
        start_row = self._table.rowCount()
        if self._run_counter > 1:
            self._table.insertRow(start_row)
            self._table.setSpan(start_row, 0, 1, 4)
            
            sep_item = QTableWidgetItem(f"   Run #{self._run_counter}  —  Tol: {self._tol:g}, Max Iter: {self._iter_spin.value()}")
            sep_item.setBackground(QBrush(QColor(Colors.BG_PANEL)))
            sep_item.setForeground(QBrush(QColor(Colors.BRAND)))
            font = sep_item.font()
            font.setBold(True)
            sep_item.setFont(font)
            sep_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._table.setItem(start_row, 0, sep_item)
            start_row += 1
            
        new_rows = len(history)
        for i in range(new_rows):
            self._table.insertRow(start_row + i)
            
        for r, mismatch in enumerate(history):
            iter_num = str(r + 1)
            is_last = (r == len(history) - 1)
            
            if is_last:
                status = "Converged \u2705" if result.converged else "Failed \u274C"
                status_color = QColor(Colors.OK if result.converged else Colors.OVER)
            else:
                status = "Active"
                status_color = QColor(Colors.TEXT_MUTED)
                
            items = [
                QTableWidgetItem(iter_num),
                QTableWidgetItem(f"{mismatch:.3e}"),
                QTableWidgetItem(f"{self._tol:g}"),
                QTableWidgetItem(status),
            ]
            
            # Apply beautiful typography and alignment
            for c, item in enumerate(items):
                item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
                if is_last:
                    item.setForeground(QBrush(status_color))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                else:
                    item.setForeground(QBrush(status_color))
                self._table.setItem(start_row + r, c, item)
        self._table.scrollToBottom()

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
