"""Tests for the backward-forward sweep solver (Sprint 2)."""
from __future__ import annotations

from pathlib import Path

from gridlens.core.models import Bus, Capacitor, Generator, Line, Load, Network
from gridlens.core.parser import load_network
from gridlens.core.solver import solve

EXAMPLE = Path(__file__).resolve().parents[1] / "data" / "examples" / "4bus_radial.json"


def _result_by_bus(result):
    return {b.bus_id: b for b in result.bus_results}


def _kcl_residual(network: Network, result) -> float:
    """Independent check: with the solver's final voltages, verify Kirchhoff's
    current law at every bus using Ohm's-law branch currents. This does not
    reuse the solver's current-summation, so it genuinely validates the answer.

    Only valid for pure-PQ networks (no operator-pinned reactive injection).
    """
    import math
    v = {}
    for b in result.bus_results:
        v[b.bus_id] = b.v_pu * complex(
            math.cos(math.radians(b.angle_deg)), math.sin(math.radians(b.angle_deg))
        )

    s_base_kw = network.base_mva * 1000.0
    p = {b.id: 0.0 for b in network.buses}
    q = {b.id: 0.0 for b in network.buses}
    b_sh = {b.id: 0.0 for b in network.buses}
    for ld in network.loads:
        p[ld.bus] += ld.p_kw / s_base_kw
        q[ld.bus] += ld.q_kvar / s_base_kw
    for g in network.generators:
        p[g.bus] -= g.p_kw / s_base_kw
        q[g.bus] -= g.q_kvar / s_base_kw
    for c in network.capacitors:
        if c.in_service:
            b_sh[c.bus] += c.q_kvar / s_base_kw

    z = {(ln.from_bus, ln.to_bus): complex(ln.r_pu, ln.x_pu) for ln in network.lines}
    z.update({(b, a): zz for (a, b), zz in z.items()})

    slack = next(b.id for b in network.buses if b.is_slack)
    incident = {b.id: [] for b in network.buses}
    for ln in network.lines:
        incident[ln.from_bus].append(ln.to_bus)
        incident[ln.to_bus].append(ln.from_bus)

    worst = 0.0
    for bus in network.buses:
        if bus.id == slack:
            continue  # slack absorbs the imbalance by definition
        bid = bus.id
        node_i = (complex(p[bid], q[bid]) / v[bid]).conjugate() + 1j * b_sh[bid] * v[bid]
        branch_sum = complex(0.0, 0.0)
        for other in incident[bid]:
            # current leaving bid toward `other`
            branch_sum += (v[bid] - v[other]) / z[(bid, other)]
        # KCL: current injected into node by branches = current drawn by devices
        residual = abs(-branch_sum - node_i)
        worst = max(worst, residual)
    return worst


# --------------------------------------------------------------------------- #
# Basic behavior
# --------------------------------------------------------------------------- #
def test_flat_network_no_load() -> None:
    net = Network(
        base_mva=10.0,
        buses=[Bus(id="A", is_slack=True), Bus(id="B")],
        lines=[Line(id="1", from_bus="A", to_bus="B", r_pu=0.01, x_pu=0.1)],
    )
    res = solve(net)
    assert res.converged
    by = _result_by_bus(res)
    assert abs(by["A"].v_pu - 1.0) < 1e-9
    assert abs(by["B"].v_pu - 1.0) < 1e-9  # no load -> no drop


def test_load_causes_voltage_drop() -> None:
    net = Network(
        base_mva=10.0,
        buses=[Bus(id="A", is_slack=True), Bus(id="B")],
        lines=[Line(id="1", from_bus="A", to_bus="B", r_pu=0.02, x_pu=0.1)],
        loads=[Load(id="L", bus="B", p_kw=500.0, q_kvar=200.0)],
    )
    res = solve(net)
    assert res.converged
    by = _result_by_bus(res)
    assert by["B"].v_pu < 1.0
    assert by["A"].v_pu == 1.0


def test_more_load_means_lower_voltage() -> None:
    def v_b(p_kw: float) -> float:
        net = Network(
            base_mva=10.0,
            buses=[Bus(id="A", is_slack=True), Bus(id="B")],
            lines=[Line(id="1", from_bus="A", to_bus="B", r_pu=0.02, x_pu=0.1)],
            loads=[Load(id="L", bus="B", p_kw=p_kw, q_kvar=0.4 * p_kw)],
        )
        return _result_by_bus(solve(net))["B"].v_pu

    assert v_b(200.0) > v_b(500.0) > v_b(900.0)


def test_capacitor_raises_voltage() -> None:
    base = Network(
        base_mva=10.0,
        buses=[Bus(id="A", is_slack=True), Bus(id="B")],
        lines=[Line(id="1", from_bus="A", to_bus="B", r_pu=0.02, x_pu=0.1)],
        loads=[Load(id="L", bus="B", p_kw=500.0, q_kvar=300.0)],
    )
    v_no_cap = _result_by_bus(solve(base))["B"].v_pu

    base.capacitors = [Capacitor(id="C", bus="B", q_kvar=200.0, in_service=True)]
    v_with_cap = _result_by_bus(solve(base))["B"].v_pu
    assert v_with_cap > v_no_cap


def test_out_of_service_capacitor_has_no_effect() -> None:
    net = Network(
        base_mva=10.0,
        buses=[Bus(id="A", is_slack=True), Bus(id="B")],
        lines=[Line(id="1", from_bus="A", to_bus="B", r_pu=0.02, x_pu=0.1)],
        loads=[Load(id="L", bus="B", p_kw=500.0, q_kvar=300.0)],
        capacitors=[Capacitor(id="C", bus="B", q_kvar=200.0, in_service=False)],
    )
    v_off = _result_by_bus(solve(net))["B"].v_pu

    net.capacitors = []
    v_none = _result_by_bus(solve(net))["B"].v_pu
    assert abs(v_off - v_none) < 1e-9


def test_generator_raises_voltage() -> None:
    net = Network(
        base_mva=10.0,
        buses=[Bus(id="A", is_slack=True), Bus(id="B")],
        lines=[Line(id="1", from_bus="A", to_bus="B", r_pu=0.02, x_pu=0.1)],
        loads=[Load(id="L", bus="B", p_kw=500.0, q_kvar=200.0)],
    )
    v_no_gen = _result_by_bus(solve(net))["B"].v_pu
    net.generators = [Generator(id="G", bus="B", p_kw=300.0, q_kvar=150.0)]
    v_gen = _result_by_bus(solve(net))["B"].v_pu
    assert v_gen > v_no_gen


# --------------------------------------------------------------------------- #
# Accuracy via independent KCL check
# --------------------------------------------------------------------------- #
def test_example_satisfies_kcl() -> None:
    net = load_network(EXAMPLE)
    # Drop the operator pin so the network is pure PQ for the KCL check.
    for b in net.buses:
        b.v_set_pu = None
    # Solve to a tight tolerance so the KCL residual reflects solver accuracy
    # rather than the (looser) default convergence threshold.
    res = solve(net, tol=1e-10)
    assert res.converged
    assert _kcl_residual(net, res) < 1e-7


def test_example_converges_and_orders() -> None:
    net = load_network(EXAMPLE)
    res = solve(net)
    assert res.converged
    by = _result_by_bus(res)
    assert abs(by["B1"].v_pu - 1.0) < 1e-9  # slack
    # All four buses solved.
    assert set(by) == {"B1", "B2", "B3", "B4"}


# --------------------------------------------------------------------------- #
# Operator-pinned leaf voltage (outer Q-compensation loop)
# --------------------------------------------------------------------------- #
def test_pinned_leaf_holds_setpoint() -> None:
    net = Network(
        base_mva=10.0,
        buses=[
            Bus(id="A", is_slack=True),
            Bus(id="B", is_leaf=True, v_set_pu=1.02),
        ],
        lines=[Line(id="1", from_bus="A", to_bus="B", r_pu=0.02, x_pu=0.1)],
        loads=[Load(id="L", bus="B", p_kw=500.0, q_kvar=200.0)],
    )
    res = solve(net)
    assert res.converged
    assert abs(_result_by_bus(res)["B"].v_pu - 1.02) < 1e-5


def test_pinned_leaf_on_example() -> None:
    net = load_network(EXAMPLE)  # B4 pinned to 1.00
    res = solve(net)
    assert res.converged
    assert abs(_result_by_bus(res)["B4"].v_pu - 1.00) < 1e-5


# --------------------------------------------------------------------------- #
# Violation flags
# --------------------------------------------------------------------------- #
def test_undervoltage_flagged() -> None:
    net = Network(
        base_mva=10.0,
        buses=[Bus(id="A", is_slack=True), Bus(id="B")],
        lines=[Line(id="1", from_bus="A", to_bus="B", r_pu=0.05, x_pu=0.2)],
        loads=[Load(id="L", bus="B", p_kw=4000.0, q_kvar=2500.0)],
    )
    res = solve(net)
    assert res.converged
    assert _result_by_bus(res)["B"].v_pu < 0.95
    assert _result_by_bus(res)["B"].violation == "under"


def test_no_slack_returns_unconverged() -> None:
    net = Network(buses=[Bus(id="A"), Bus(id="B")])
    res = solve(net)
    assert not res.converged
    assert "slack" in res.message.lower()
