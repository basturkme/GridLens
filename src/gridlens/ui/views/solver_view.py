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


class _FlatStep:
    """Single-outer-pass shim so the table can render results that predate the
    solver's `steps` trajectory (only a flat `mismatch_history` is available)."""

    __slots__ = ("outer", "inner", "max_dv", "pinned_err")

    def __init__(self, inner: int, max_dv: float) -> None:
        self.outer = 1
        self.inner = inner
        self.max_dv = max_dv
        self.pinned_err = None


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
        # NOTE: the up/down sub-controls must be positioned explicitly. With only
        # `padding` set, Qt collapses the up-button's clickable rect to zero height
        # (down still works) — so we anchor both buttons to the border box. Two
        # further quirks: giving a button its own `border`/`border-radius` makes
        # Qt stop drawing the native arrow, and the arrow needs an explicit size
        # to render once the button is styled. So: position the buttons, size the
        # arrows, and tint on hover only (no per-button border).
        self._iter_spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {Colors.BG};
                border: 1px solid {Colors.BORDER};
                color: {Colors.TEXT};
                padding: 4px;
                padding-right: 22px;
                border-radius: 4px;
            }}
            QSpinBox::up-button {{
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 20px;
            }}
            QSpinBox::down-button {{
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 20px;
            }}
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
                background-color: {Colors.BRAND_LIGHT};
            }}
            QSpinBox::up-arrow {{ width: 10px; height: 10px; }}
            QSpinBox::down-arrow {{ width: 10px; height: 10px; }}
        """)
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

        flow_title = QLabel("VA Approach — Power-Summation Sweep")
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
        flow_layout.addWidget(make_step("2", "Backward Sweep (VA)", "Accumulate branch power S = P + jQ from leaves to root (incl. losses)"))
        flow_layout.addWidget(make_arrow())
        flow_layout.addWidget(make_step("3", "Forward Sweep", "Recover I = (S / V)* and update voltages from root to leaves"))
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
        clbl = QLabel("4. Inner Convergence Check")
        clbl.setStyleSheet(f"font-weight: bold; color: {Colors.BRAND}; border: none;")
        csub = QLabel("Is Max |ΔV_i| < Tolerance?")
        csub.setStyleSheet(f"font-size: 8pt; color: {Colors.TEXT_MUTED}; border: none;")
        cfl.addWidget(clbl)
        cfl.addWidget(csub)
        flow_layout.addWidget(check_step)

        inner_loop = QLabel("↺ Inner loop: back to Step 2 while |ΔV| > tolerance")
        inner_loop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inner_loop.setStyleSheet(f"font-size: 8pt; font-style: italic; color: {Colors.TEXT_MUTED}; border: none; margin-top: 4px;")
        flow_layout.addWidget(inner_loop)

        flow_layout.addWidget(make_arrow())
        flow_layout.addWidget(make_step(
            "5", "Pinned |V| Check (outer loop)",
            "Only if a bus voltage is pinned: is |V_set − |V|| < tol?\n"
            "If not, adjust injected Q (ΔQ ≈ ΔV / X_th) and re-sweep.",
        ))

        outer_loop = QLabel("↺ Outer loop: back to Step 2 until pinned |V| is held")
        outer_loop.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer_loop.setStyleSheet(f"font-size: 8pt; font-style: italic; color: {Colors.BRAND_HOVER}; border: none; margin-top: 4px;")
        flow_layout.addWidget(outer_loop)

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

        history_header = QHBoxLayout()
        history_header.addWidget(QLabel("Iteration steps & mismatch history"))
        history_header.addStretch(1)
        self._clear_btn = QPushButton("Clear history")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setToolTip("Clear the convergence log and iteration table")
        self._clear_btn.clicked.connect(self._clear_history)
        history_header.addWidget(self._clear_btn)
        right_layout.addLayout(history_header)

        # Columns: Outer pass | inner iteration | max |ΔV| | pinned |V| error |
        # tolerance | status. The Outer / Pinned columns only matter when the
        # network has a voltage-controlled (pinned) bus, so they start hidden and
        # are revealed the first time a run actually exercises the outer loop.
        self._COL_OUTER, self._COL_ITER, self._COL_DV = 0, 1, 2
        self._COL_PINNED, self._COL_TOL, self._COL_STATUS = 3, 4, 5
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Outer", "Iteration", "Max |ΔV| (pu)", "Pinned |V| err", "Tolerance (pu)", "Status"]
        )
        self._table.setColumnHidden(self._COL_OUTER, True)
        self._table.setColumnHidden(self._COL_PINNED, True)
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
        self._log.clear()
        self._table.setRowCount(0)
        self._table.setColumnHidden(self._COL_OUTER, True)
        self._table.setColumnHidden(self._COL_PINNED, True)
        self._run_counter = 0
        if network is not None and solution is not None:
            self.show_result(solution)

    def show_result(self, result: SolutionResult) -> None:
        formatted = self._format(result)
        if self._run_counter == 0:
            self._log.setPlainText(formatted)
        else:
            self._log.append("\n" + "—" * 45 + "\n\n" + formatted)
        self._populate_table(result)

    def _clear_history(self) -> None:
        """Wipe the convergence log and iteration table, resetting the run count
        so the next solve starts a fresh history."""
        self._log.clear()
        self._table.setRowCount(0)
        self._table.setColumnHidden(self._COL_OUTER, True)
        self._table.setColumnHidden(self._COL_PINNED, True)
        self._run_counter = 0

    # -- internals ---------------------------------------------------------- #
    def _on_tol_changed(self, value: float) -> None:
        self._tol = value

    def _emit_solve(self) -> None:
        self.solveRequested.emit(self._tol, self._iter_spin.value())

    def _populate_table(self, result: SolutionResult) -> None:
        # The full trajectory spans every outer Q-compensation pass; fall back to
        # the flat inner history for older results that predate `steps`.
        steps = list(getattr(result, "steps", None) or [])
        if not steps:
            steps = [
                _FlatStep(i + 1, m)
                for i, m in enumerate(getattr(result, "mismatch_history", []))
            ]
        if not steps:
            return

        has_outer = any(s.pinned_err is not None for s in steps)
        if has_outer:
            # A pinned bus exercised the outer loop — reveal the extra columns.
            self._table.setColumnHidden(self._COL_OUTER, False)
            self._table.setColumnHidden(self._COL_PINNED, False)

        self._run_counter += 1
        start_row = self._table.rowCount()
        if self._run_counter > 1:
            label = f"   Run #{self._run_counter}  —  Tol: {self._tol:g}, Max Iter: {self._iter_spin.value()}"
            if has_outer:
                label += f", Outer passes: {getattr(result, 'outer_iterations', 1)}"
            self._table.insertRow(start_row)
            self._table.setSpan(start_row, 0, 1, self._table.columnCount())
            sep_item = QTableWidgetItem(label)
            sep_item.setBackground(QBrush(QColor(Colors.BG_PANEL)))
            sep_item.setForeground(QBrush(QColor(Colors.BRAND)))
            font = sep_item.font()
            font.setBold(True)
            sep_item.setFont(font)
            sep_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._table.setItem(start_row, 0, sep_item)
            start_row += 1

        for i in range(len(steps)):
            self._table.insertRow(start_row + i)

        for r, step in enumerate(steps):
            is_last = (r == len(steps) - 1)
            # A pass boundary = the outer index changes on the next step (or this
            # is the very last step): the inner sweep converged and the outer loop
            # is about to nudge Q unless we are already done.
            is_pass_end = is_last or steps[r + 1].outer != step.outer

            if is_last:
                status = "Converged \u2705" if result.converged else "Failed \u274C"
                status_color = QColor(Colors.OK if result.converged else Colors.OVER)
            elif is_pass_end:
                status = "Q-adjust \u21BA"
                status_color = QColor(Colors.BRAND_HOVER)
            else:
                status = "Active"
                status_color = QColor(Colors.TEXT_MUTED)

            pinned_txt = "\u2014" if step.pinned_err is None else f"{step.pinned_err:.3e}"
            cells = {
                self._COL_OUTER: str(step.outer),
                self._COL_ITER: str(step.inner),
                self._COL_DV: f"{step.max_dv:.3e}",
                self._COL_PINNED: pinned_txt,
                self._COL_TOL: f"{self._tol:g}",
                self._COL_STATUS: status,
            }
            for col, text in cells.items():
                item = QTableWidgetItem(text)
                item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter))
                item.setForeground(QBrush(status_color))
                if is_last:
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self._table.setItem(start_row + r, col, item)
        self._table.scrollToBottom()

    def _format(self, result: SolutionResult) -> str:
        lines = [
            "Power flow result",
            f"  Status:        {'Converged' if result.converged else 'NOT converged'}",
            f"  Iterations:    {result.iterations} (inner, final pass)",
            f"  Max mismatch:  {result.max_mismatch:.3e} pu",
            f"  Message:       {result.message}",
        ]
        outer = getattr(result, "outer_iterations", 1)
        if outer > 1:
            lines.append(
                f"  Outer passes:  {outer} (Q-compensation to hold pinned |V|)"
            )
        q_inj = getattr(result, "pinned_q_inject_kvar", {})
        for bus, kvar in q_inj.items():
            # Reactive support the pinned bus needed — sign convention: positive =
            # injected (capacitive) to lift |V|, negative = absorbed (inductive).
            verb = "inject" if kvar >= 0 else "absorb"
            lines.append(
                f"  Reqd Q @ {bus}:  {abs(kvar):.1f} kvar ({verb}) to hold its pinned |V|"
            )
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
