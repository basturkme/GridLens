"""Headless tests for the on-the-fly equipment editor (Sprint 4)."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

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


def _fields(editor):
    from gridlens.ui.widgets.numeric_field import NumericField

    return editor.findChildren(NumericField)


def _checkbox(editor):
    from PyQt6.QtWidgets import QCheckBox

    return editor.findChildren(QCheckBox)[0]


# --------------------------------------------------------------------------- #
# Model mutation + signal
# --------------------------------------------------------------------------- #
def test_edit_load_power_mutates_model_and_signals(qapp) -> None:
    from gridlens.ui.views.equipment_view import EquipmentView

    net = _demo()
    view = EquipmentView()
    view.set_network(net, solve(net))

    edits: list[int] = []
    view.networkEdited.connect(lambda: edits.append(1))

    editor = view._editor_for("load", "Ld4")
    view._set_editor(editor)
    p_field, q_field = _fields(editor)
    p_field.setText("400")
    q_field.setText("250")

    load = next(x for x in net.loads if x.id == "Ld4")
    assert load.p_kw == 400.0
    assert load.q_kvar == 250.0
    assert len(edits) >= 2


def test_invalid_input_does_not_mutate(qapp) -> None:
    from gridlens.ui.views.equipment_view import EquipmentView

    net = _demo()
    view = EquipmentView()
    view.set_network(net, solve(net))

    editor = view._editor_for("load", "Ld4")
    view._set_editor(editor)
    p_field, _ = _fields(editor)
    p_field.setText("not a number")

    load = next(x for x in net.loads if x.id == "Ld4")
    assert load.p_kw == 150.0  # unchanged
    assert p_field.property("invalid") == "true"


def test_capacitor_in_service_toggle(qapp) -> None:
    from gridlens.ui.views.equipment_view import EquipmentView

    net = _demo()
    view = EquipmentView()
    view.set_network(net, solve(net))

    editor = view._editor_for("cap", "C3")
    view._set_editor(editor)
    box = _checkbox(editor)
    assert box.isChecked()
    box.setChecked(False)

    cap = net.capacitors[0]
    assert cap.in_service is False


def test_leaf_pin_unpin(qapp) -> None:
    from gridlens.ui.views.equipment_view import EquipmentView

    net = _demo()
    view = EquipmentView()
    view.set_network(net, solve(net))

    editor = view._editor_for("bus", "B4")
    view._set_editor(editor)
    hold = _checkbox(editor)
    assert hold.isChecked()  # B4 starts pinned

    hold.setChecked(False)
    bus = next(b for b in net.buses if b.id == "B4")
    assert bus.v_set_pu is None


# --------------------------------------------------------------------------- #
# Live re-solve loop through the shell
# --------------------------------------------------------------------------- #
def test_unpinning_leaf_through_shell_resolves_and_droops(qapp) -> None:
    from gridlens.ui.main_window import MainWindow

    net = _demo()
    win = MainWindow()
    win.set_network(net, solve(net))

    eq = win._pages["equipment"]
    editor = eq._editor_for("bus", "B4")
    eq._set_editor(editor)

    # While pinned, B4 sits at the setpoint.
    b4 = next(b for b in win._solution.bus_results if b.bus_id == "B4")
    assert abs(b4.v_pu - 1.0) < 1e-4

    # Unpin -> shell re-solves -> B4 now droops below 1.0 under load.
    _checkbox(editor).setChecked(False)
    b4 = next(b for b in win._solution.bus_results if b.bus_id == "B4")
    assert b4.v_pu < 1.0


def test_heavier_load_through_shell_lowers_voltage(qapp) -> None:
    from gridlens.ui.main_window import MainWindow

    net = _demo()
    # Unpin the leaf so its voltage is free to move with load.
    next(b for b in net.buses if b.id == "B4").v_set_pu = None
    win = MainWindow()
    win.set_network(net, solve(net))
    v_before = next(b for b in win._solution.bus_results if b.bus_id == "B4").v_pu

    eq = win._pages["equipment"]
    editor = eq._editor_for("load", "Ld4")
    eq._set_editor(editor)
    p_field, q_field = _fields(editor)
    p_field.setText("3000")
    q_field.setText("2000")

    v_after = next(b for b in win._solution.bus_results if b.bus_id == "B4").v_pu
    assert v_after < v_before


def test_clicking_bus_on_diagram_highlights_without_navigating(qapp) -> None:
    from gridlens.ui.main_window import MainWindow

    net = _demo()
    win = MainWindow()
    win.set_network(net, solve(net))
    start_page = win._stack.currentWidget()

    # Simulate selecting a bus on the Network diagram.
    win._pages["network"]._sld._bus_items["B4"].setSelected(True)

    # A bus click highlights the bus and reports it on the status bar, but
    # navigation to the Equipment editor is reserved for equipment symbols /
    # the Details button (see MainWindow._on_bus_picked) — so the page stays put.
    assert win._stack.currentWidget() is start_page
    assert win._stack.currentWidget() is not win._pages["equipment"]
    assert "B4" in win.statusBar().currentMessage()


def test_clicking_equipment_symbol_opens_its_editor(qapp) -> None:
    from gridlens.ui.main_window import MainWindow
    from gridlens.ui.sld.items import CapacitorItem, LoadItem

    net = _demo()
    win = MainWindow()
    win.set_network(net, solve(net))

    scene = win._pages["network"]._sld._scene
    load_item = next(i for i in scene.items() if isinstance(i, LoadItem))
    load_item.setSelected(True)

    assert win._stack.currentWidget() is win._pages["equipment"]
    eq = win._pages["equipment"]
    from gridlens.ui.views.equipment_view import _ID_ROLE, _KIND_ROLE

    current = eq._tree.currentItem()
    assert current.data(0, _KIND_ROLE) == "load"
    assert current.data(0, _ID_ROLE) == "Ld4"

    # And a capacitor symbol routes to the capacitor editor.
    scene.clearSelection()
    cap_item = next(i for i in scene.items() if isinstance(i, CapacitorItem))
    cap_item.setSelected(True)
    current = eq._tree.currentItem()
    assert current.data(0, _KIND_ROLE) == "cap"
    assert current.data(0, _ID_ROLE) == "C3"
