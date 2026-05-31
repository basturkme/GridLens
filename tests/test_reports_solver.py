"""Headless tests for the Solver and Reports views (Sprint 6)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("matplotlib")

from gridlens.core.models import (  # noqa: E402
    Bus,
    Capacitor,
    Generator,
    Line,
    Load,
    Network,
)
from gridlens.core.solver import solve  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _demo() -> Network:
    return Network(
        name="demo",
        base_mva=10.0,
        buses=[
            Bus(id="B1", name="Bus 1", base_kv=33.0, is_slack=True),
            Bus(id="B2", name="Bus 2", base_kv=11.0),
            Bus(id="B3", name="Bus 3", base_kv=11.0),
            Bus(id="B4", name="Bus 4", base_kv=11.0, is_leaf=True, v_set_pu=1.0),
        ],
        lines=[
            Line(id="T1", from_bus="B1", to_bus="B2", r_pu=0.005, x_pu=0.10),
            Line(id="L23", from_bus="B2", to_bus="B3", r_pu=0.02, x_pu=0.06),
            Line(id="L34", from_bus="B3", to_bus="B4", r_pu=0.025, x_pu=0.07),
        ],
        loads=[Load(id="Ld4", bus="B4", p_kw=150.0, q_kvar=50.0)],
        generators=[Generator(id="G2", bus="B2", p_kw=100.0)],
        capacitors=[Capacitor(id="C3", bus="B3", q_kvar=50.0, in_service=True)],
    )


# --------------------------------------------------------------------------- #
# Solver view
# --------------------------------------------------------------------------- #
def test_solver_view_shows_result(qapp) -> None:
    from gridlens.ui.views.solver_view import SolverView

    net = _demo()
    view = SolverView()
    view.set_network(net, solve(net))
    assert view._run_btn.isEnabled()
    text = view._log.toPlainText()
    assert "Converged" in text
    assert "Iterations" in text


def test_solver_view_disabled_without_network(qapp) -> None:
    from gridlens.ui.views.solver_view import SolverView

    view = SolverView()
    assert not view._run_btn.isEnabled()
    view.set_network(None)
    assert not view._run_btn.isEnabled()


def test_solver_view_emits_request_with_params(qapp) -> None:
    from gridlens.ui.views.solver_view import SolverView

    view = SolverView()
    view.set_network(_demo(), None)

    got: list[tuple[float, int]] = []
    view.solveRequested.connect(lambda t, i: got.append((t, i)))

    view._tol_field.setText("1e-4")
    view._iter_spin.setValue(33)
    view._run_btn.click()

    assert got
    tol, max_iter = got[0]
    assert max_iter == 33
    assert abs(tol - 1e-4) < 1e-12


# --------------------------------------------------------------------------- #
# Reports view
# --------------------------------------------------------------------------- #
def test_reports_table_populates(qapp) -> None:
    from gridlens.ui.views.reports_view import ReportsView

    net = _demo()
    view = ReportsView()
    view.set_network(net, solve(net))

    assert view._table.rowCount() == 4
    assert view._table.item(0, 0).text() == "B1"
    # |V| (kV) column = v_pu * base_kv; B1 is the 33 kV slack at ~1.0 pu.
    kv = float(view._table.item(0, 3).text())
    assert abs(kv - 33.0) < 0.5
    assert view._export_btn.isEnabled()


def test_reports_export_csv(qapp, tmp_path: Path) -> None:
    from gridlens.ui.views.reports_view import ReportsView

    net = _demo()
    view = ReportsView()
    view.set_network(net, solve(net))

    out = tmp_path / "v.csv"
    view.export_csv(out)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("Bus")
    assert len(lines) == 1 + len(net.buses)


def test_reports_empty_network(qapp) -> None:
    from gridlens.ui.views.reports_view import ReportsView

    view = ReportsView()
    view.set_network(None)
    assert view._table.rowCount() == 0
    assert not view._export_btn.isEnabled()
    # Chart still renders its "no solution" placeholder without error.
    assert view._ax is not None


# --------------------------------------------------------------------------- #
# Shell integration
# --------------------------------------------------------------------------- #
def test_shell_distributes_solution_to_solver_and_reports(qapp) -> None:
    from gridlens.ui.main_window import MainWindow

    win = MainWindow()
    net = _demo()
    win.set_network(net, solve(net))

    assert win._pages["reports"]._table.rowCount() == 4
    assert win._pages["solver"]._run_btn.isEnabled()
    assert "Converged" in win._pages["solver"]._log.toPlainText()


def test_shell_handles_solve_request(qapp) -> None:
    from gridlens.ui.main_window import MainWindow

    win = MainWindow()
    win.set_network(_demo(), None)

    win._pages["solver"].solveRequested.emit(1e-6, 25)
    assert win._tol == 1e-6
    assert win._max_iter == 25
    assert win._solution is not None and win._solution.converged
    assert win._pages["reports"]._table.rowCount() == 4
