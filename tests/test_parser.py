"""Tests for the network file parser (Sprint 1)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gridlens.core.models import Bus, Capacitor, Generator, Line, Load, Network
from gridlens.core.parser import (
    ParserError,
    load_network,
    save_network,
    validate_network,
)

EXAMPLE = Path(__file__).resolve().parents[1] / "data" / "examples" / "4bus_radial.json"


def _valid_network() -> Network:
    return Network(
        name="t",
        base_mva=10.0,
        buses=[
            Bus(id="B1", is_slack=True),
            Bus(id="B2"),
            Bus(id="B3", is_leaf=True, v_set_pu=1.0),
        ],
        lines=[
            Line(id="T1", from_bus="B1", to_bus="B2", x_pu=0.1),
            Line(id="L23", from_bus="B2", to_bus="B3", x_pu=0.06),
        ],
        loads=[Load(id="Ld3", bus="B3", p_kw=150.0, q_kvar=50.0)],
        generators=[Generator(id="G2", bus="B2", p_kw=100.0)],
        capacitors=[Capacitor(id="C3", bus="B3", q_kvar=50.0)],
    )


# --------------------------------------------------------------------------- #
# Loading the shipped example
# --------------------------------------------------------------------------- #
def test_load_example_file() -> None:
    net = load_network(EXAMPLE)
    assert net.name.startswith("4-bus")
    assert net.base_mva == 10.0
    assert [b.id for b in net.buses] == ["B1", "B2", "B3", "B4"]
    assert len(net.lines) == 3
    slack = [b for b in net.buses if b.is_slack]
    assert len(slack) == 1 and slack[0].id == "B1"
    leaf = next(b for b in net.buses if b.is_leaf)
    assert leaf.id == "B4" and leaf.v_set_pu == 1.0


# --------------------------------------------------------------------------- #
# Round-trip
# --------------------------------------------------------------------------- #
def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    original = _valid_network()
    out = tmp_path / "net.json"
    save_network(original, out)
    reloaded = load_network(out)

    assert reloaded.name == original.name
    assert reloaded.base_mva == original.base_mva
    assert [b.id for b in reloaded.buses] == [b.id for b in original.buses]
    leaf = next(b for b in reloaded.buses if b.is_leaf)
    assert leaf.v_set_pu == 1.0
    assert reloaded.loads[0].p_kw == 150.0
    assert reloaded.capacitors[0].in_service is True


def test_example_roundtrips(tmp_path: Path) -> None:
    net = load_network(EXAMPLE)
    out = tmp_path / "rt.json"
    save_network(net, out)
    again = load_network(out)
    assert [b.id for b in again.buses] == [b.id for b in net.buses]
    assert [ln.id for ln in again.lines] == [ln.id for ln in net.lines]


# --------------------------------------------------------------------------- #
# Defaults / optional fields
# --------------------------------------------------------------------------- #
def test_minimal_bus_defaults(tmp_path: Path) -> None:
    p = tmp_path / "m.json"
    p.write_text(
        json.dumps(
            {
                "buses": [{"id": "A", "is_slack": True}, {"id": "B"}],
                "lines": [{"id": "x", "from_bus": "A", "to_bus": "B"}],
            }
        ),
        encoding="utf-8",
    )
    net = load_network(p)
    assert net.buses[1].base_kv == 1.0
    assert net.buses[1].is_slack is False
    assert net.buses[1].v_set_pu is None
    assert net.lines[0].r_pu == 0.0


# --------------------------------------------------------------------------- #
# Error handling
# --------------------------------------------------------------------------- #
def test_missing_file() -> None:
    with pytest.raises(ParserError, match="File not found"):
        load_network("does_not_exist_12345.json")


def test_invalid_json(tmp_path: Path) -> None:
    p = tmp_path / "bad.json"
    p.write_text("{ not valid json ", encoding="utf-8")
    with pytest.raises(ParserError, match="Invalid JSON"):
        load_network(p)


def test_top_level_not_object(tmp_path: Path) -> None:
    p = tmp_path / "arr.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ParserError, match="must be a JSON object"):
        load_network(p)


def test_missing_required_field(tmp_path: Path) -> None:
    p = tmp_path / "n.json"
    p.write_text(json.dumps({"buses": [{"name": "no id"}]}), encoding="utf-8")
    with pytest.raises(ParserError, match="missing required field 'id'"):
        load_network(p)


def test_bool_not_accepted_as_number(tmp_path: Path) -> None:
    p = tmp_path / "n.json"
    p.write_text(
        json.dumps({"buses": [{"id": "A", "base_kv": True, "is_slack": True}]}),
        encoding="utf-8",
    )
    with pytest.raises(ParserError, match="must be a number"):
        load_network(p)


def test_wrong_type_for_number(tmp_path: Path) -> None:
    p = tmp_path / "n.json"
    p.write_text(
        json.dumps({"buses": [{"id": "A", "base_kv": "lots", "is_slack": True}]}),
        encoding="utf-8",
    )
    with pytest.raises(ParserError, match="must be a number"):
        load_network(p)


# --------------------------------------------------------------------------- #
# Network-level validation
# --------------------------------------------------------------------------- #
def test_no_slack() -> None:
    net = _valid_network()
    net.buses[0].is_slack = False
    with pytest.raises(ParserError, match="No slack bus"):
        validate_network(net)


def test_multiple_slack() -> None:
    net = _valid_network()
    net.buses[1].is_slack = True
    with pytest.raises(ParserError, match="Multiple slack buses"):
        validate_network(net)


def test_duplicate_bus_id() -> None:
    net = _valid_network()
    net.buses[1].id = "B1"
    with pytest.raises(ParserError, match="Duplicate bus id"):
        validate_network(net)


def test_dangling_line_reference() -> None:
    net = _valid_network()
    net.lines[0].to_bus = "GHOST"
    with pytest.raises(ParserError, match="unknown bus 'GHOST'"):
        validate_network(net)


def test_dangling_load_reference() -> None:
    net = _valid_network()
    net.loads[0].bus = "GHOST"
    with pytest.raises(ParserError, match="unknown bus 'GHOST'"):
        validate_network(net)


def test_too_many_buses() -> None:
    buses = [Bus(id=f"B{i}", is_slack=(i == 0)) for i in range(11)]
    lines = [Line(id=f"L{i}", from_bus=f"B{i}", to_bus=f"B{i+1}") for i in range(10)]
    net = Network(buses=buses, lines=lines)
    with pytest.raises(ParserError, match="maximum supported is 10"):
        validate_network(net)


def test_not_radial_has_loop() -> None:
    # 3 buses, 3 lines -> one extra edge forms a loop.
    net = Network(
        buses=[Bus(id="A", is_slack=True), Bus(id="B"), Bus(id="C")],
        lines=[
            Line(id="1", from_bus="A", to_bus="B"),
            Line(id="2", from_bus="B", to_bus="C"),
            Line(id="3", from_bus="C", to_bus="A"),
        ],
    )
    with pytest.raises(ParserError, match="not radial"):
        validate_network(net)


def test_disconnected_network() -> None:
    # 4 buses but only 2 lines connecting 3 of them, plus a duplicate edge count
    # would be wrong — instead build buses-1 lines that leave one island.
    net = Network(
        buses=[Bus(id="A", is_slack=True), Bus(id="B"), Bus(id="C"), Bus(id="D")],
        lines=[
            Line(id="1", from_bus="A", to_bus="B"),
            Line(id="2", from_bus="A", to_bus="C"),
            Line(id="3", from_bus="B", to_bus="C"),  # loop in {A,B,C}, D isolated
        ],
    )
    with pytest.raises(ParserError, match="not connected"):
        validate_network(net)


def test_self_loop_line() -> None:
    net = _valid_network()
    net.lines[0].to_bus = net.lines[0].from_bus
    with pytest.raises(ParserError, match="to itself"):
        validate_network(net)


def test_v_set_on_non_leaf() -> None:
    net = _valid_network()
    net.buses[1].v_set_pu = 1.02  # B2 is not a leaf
    with pytest.raises(ParserError, match="not a leaf"):
        validate_network(net)
