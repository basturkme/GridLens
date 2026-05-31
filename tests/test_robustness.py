"""Sprint 7 — robustness & graceful-degradation tests.

Covers both the pure solver (no Qt) and the shell's handling of pathological
operating points.
"""
from __future__ import annotations

import math
import os

import pytest

from gridlens.core.models import Bus, Generator, Line, Load, Network
from gridlens.core.solver import solve


# --------------------------------------------------------------------------- #
# Solver: never raises, reports non-convergence
# --------------------------------------------------------------------------- #
def _two_bus(p_kw: float, q_kvar: float = 0.0) -> Network:
    return Network(
        base_mva=10.0,
        buses=[Bus(id="A", is_slack=True), Bus(id="B")],
        lines=[Line(id="1", from_bus="A", to_bus="B", r_pu=0.05, x_pu=0.2)],
        loads=[Load(id="L", bus="B", p_kw=p_kw, q_kvar=q_kvar)],
    )


def test_absurd_load_does_not_raise_and_reports_failure() -> None:
    # Far beyond the feeder's loadability — must not raise, must flag failure.
    res = solve(_two_bus(1e9, 5e8))
    assert res.converged is False
    assert res.message  # non-empty explanation
    # Voltages are reported as NaN rather than inf/garbage.
    assert all(math.isnan(b.v_pu) or b.v_pu >= 0 for b in res.bus_results)


def test_diverged_message_mentions_loadability() -> None:
    res = solve(_two_bus(1e9))
    assert res.converged is False
    assert "diverged" in res.message.lower() or "loadability" in res.message.lower()


def test_iteration_limit_not_diverged() -> None:
    # A solvable network but with too few iterations: not converged, not NaN.
    net = _two_bus(800.0, 400.0)
    res = solve(net, max_iter=1)
    assert res.converged is False
    assert all(math.isfinite(b.v_pu) for b in res.bus_results)
    assert "iteration" in res.message.lower()


def test_single_bus_network_trivially_converges() -> None:
    net = Network(base_mva=10.0, buses=[Bus(id="S", is_slack=True)])
    res = solve(net)
    assert res.converged
    assert abs(res.bus_results[0].v_pu - 1.0) < 1e-9


def test_no_load_network_is_flat() -> None:
    net = Network(
        base_mva=10.0,
        buses=[Bus(id="A", is_slack=True), Bus(id="B")],
        lines=[Line(id="1", from_bus="A", to_bus="B", x_pu=0.1)],
        generators=[Generator(id="G", bus="B")],
    )
    res = solve(net)
    assert res.converged
    assert all(abs(b.v_pu - 1.0) < 1e-9 for b in res.bus_results)


# --------------------------------------------------------------------------- #
# Shell: pathological edits and non-convergence surface in the UI
# --------------------------------------------------------------------------- #
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_qt = pytest.importorskip("PyQt6")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_network_view_shows_banner_when_not_converged(qapp) -> None:
    from gridlens.ui.views.network_view import NetworkView

    net = _two_bus(150.0)
    view = NetworkView()
    view.set_network(net, solve(net))
    assert view._warning.isHidden()  # healthy solve -> no banner

    bad = _two_bus(1e9)
    view.set_network(bad, solve(bad))
    assert not view._warning.isHidden()
    assert "did not converge" in view._warning.text().lower()


def test_extreme_edit_through_shell_does_not_crash(qapp) -> None:
    from gridlens.ui.main_window import MainWindow

    net = _two_bus(150.0)
    win = MainWindow()
    win.set_network(net, solve(net))

    # Drive an absurd load straight through the equipment editor.
    eq = win._pages["equipment"]
    editor = eq._editor_for("load", "L")
    eq._set_editor(editor)
    from gridlens.ui.widgets.numeric_field import NumericField

    p_field = editor.findChildren(NumericField)[0]
    p_field.setText("1000000000")  # 1e9 kW

    # No exception; shell reports non-convergence everywhere.
    assert win._solution is not None
    assert win._solution.converged is False
    assert not win._pages["network"]._warning.isHidden()
    assert "not converge" in win.statusBar().currentMessage().lower()
