"""Headless tests for the single-line-diagram rendering (Sprint 3).

These drive real PyQt6 widgets under the offscreen platform, so they need no
display. Skipped automatically if PyQt6 isn't installed.
"""
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


def _demo_network() -> Network:
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
        loads=[
            Load(id="Ld3", bus="B3", p_kw=200.0, q_kvar=60.0),
            Load(id="Ld4", bus="B4", p_kw=150.0, q_kvar=50.0),
        ],
        generators=[Generator(id="G2", bus="B2", p_kw=100.0)],
        capacitors=[Capacitor(id="C3", bus="B3", q_kvar=50.0, in_service=True)],
    )


def _item_counts(scene) -> dict[str, int]:
    from collections import Counter

    return dict(Counter(type(i).__name__ for i in scene.items()))


def test_build_scene_item_counts(qapp) -> None:
    from PyQt6.QtWidgets import QGraphicsScene

    from gridlens.ui.sld import build_scene

    net = _demo_network()
    scene = QGraphicsScene()
    bus_items = build_scene(scene, net, solve(net))

    assert sorted(bus_items) == ["B1", "B2", "B3", "B4"]
    counts = _item_counts(scene)
    assert counts["BusItem"] == 4
    assert counts["BranchItem"] == 3
    assert counts["LoadItem"] == 2
    assert counts["GeneratorItem"] == 1
    assert counts["CapacitorItem"] == 1
    assert counts["GridItem"] == 1
    # A winding change (33 kV -> 11 kV across B1->B2) draws a transformer.
    assert counts["TransformerItem"] == 1


def test_empty_network_shows_placeholder(qapp) -> None:
    from PyQt6.QtWidgets import QGraphicsScene

    from gridlens.ui.sld import build_scene

    scene = QGraphicsScene()
    items = build_scene(scene, None)
    assert items == {}
    assert len(scene.items()) == 1  # the placeholder text


def test_no_transformer_when_same_base_kv(qapp) -> None:
    from PyQt6.QtWidgets import QGraphicsScene

    from gridlens.ui.sld import build_scene

    net = Network(
        base_mva=10.0,
        buses=[
            Bus(id="A", base_kv=11.0, is_slack=True),
            Bus(id="B", base_kv=11.0),
        ],
        lines=[Line(id="1", from_bus="A", to_bus="B", x_pu=0.1)],
    )
    scene = QGraphicsScene()
    build_scene(scene, net)
    assert "TransformerItem" not in _item_counts(scene)


def test_network_view_selection_roundtrip(qapp) -> None:
    from gridlens.ui.views.network_view import NetworkView

    net = _demo_network()
    view = NetworkView()
    view.set_network(net, solve(net))

    picked: list[str] = []
    view.busPicked.connect(picked.append)

    # Canvas selection emits busPicked.
    view._sld._bus_items["B3"].setSelected(True)
    assert picked == ["B3"]

    # External drive selects without re-emitting.
    picked.clear()
    view._sld.select_bus("B2")
    assert view._sld._bus_items["B2"].isSelected()
    assert picked == []


def test_network_view_filter_matches_name_and_id(qapp) -> None:
    from gridlens.ui.views.network_view import NetworkView

    view = NetworkView()
    view.set_network(_demo_network())
    buses_node = view._tree.topLevelItem(0)

    def visible_count() -> int:
        return sum(
            1
            for j in range(buses_node.childCount())
            if not buses_node.child(j).isHidden()
        )

    view._search.setText("B4")  # matches by id even though the row shows "Bus 4"
    assert visible_count() == 1
    view._search.setText("Bus")  # matches every bus by name
    assert visible_count() == 4
    view._search.setText("")  # cleared -> all visible
    assert visible_count() == 4
