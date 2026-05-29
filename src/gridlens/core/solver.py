"""VA (Backward-Forward Sweep) power-flow solver for radial distribution networks.

The radial topology lets us avoid building/inverting a Y-bus: we order buses by
depth from the slack root, then alternate two sweeps until the bus voltages stop
moving.

  1. Order buses by depth from the slack root (BFS traversal of the radial tree).
  2. **Backward sweep** — from leaves toward root, accumulate branch currents
     I_branch = Σ_downstream [conj((P_load - P_gen + j(Q_load - Q_gen)) / V_to)]
              + jB_shunt · V_to    (capacitors / line charging as shunt susceptance,
                                    B>0 capacitive → supplies reactive power)
  3. **Forward sweep** — from root toward leaves, update voltages
     V_to = V_from − Z_branch · I_branch
  4. Repeat until max|V_k − V_{k-1}| < tol or iter > max_iter.

Operator-pinned leaf voltage (Bus.v_set_pu):
  Plain BFS converges with PQ buses + a single slack. A bus whose |V| is fixed
  (the operator pins a leaf voltage) needs an outer Q-compensation loop:
    a) Treat the pinned bus as PQ with an initial reactive injection guess.
    b) After each inner BFS converges, read the resulting |V| and compute
       ΔV = V_set − |V|.
    c) Nudge the injected Q via the Thévenin-reactance sensitivity ΔQ ≈ ΔV / X_th.
    d) Repeat until |ΔV| < tol.
  Generators in this model are pure PQ injections (no regulated |V|), so the only
  voltage-regulated element is the pinned leaf.

Capacitor banks are modeled as shunt susceptances toggled by `in_service`.
"""
from __future__ import annotations

import cmath
import math
from collections import defaultdict, deque

from gridlens.core.models import BusSolution, Network, SolutionResult
from gridlens.utils.constants import (
    DEFAULT_MAX_ITER,
    DEFAULT_TOLERANCE_PU,
    V_MAX_PU,
    V_MIN_PU,
)

_MAX_OUTER_ITER = 40
_OUTER_DAMPING = 0.8


def solve(
    network: Network,
    *,
    tol: float = DEFAULT_TOLERANCE_PU,
    max_iter: int = DEFAULT_MAX_ITER,
) -> SolutionResult:
    """Run BFS power flow on a radial network. Returns voltage magnitude/angle per bus."""
    if not network.buses:
        return SolutionResult(
            converged=False, iterations=0, max_mismatch=0.0,
            message="Network has no buses.",
        )

    slack = next((b for b in network.buses if b.is_slack), None)
    if slack is None:
        return SolutionResult(
            converged=False, iterations=0, max_mismatch=0.0,
            message="No slack bus defined.",
        )

    topo = _build_topology(network, slack.id)
    if topo is None:
        return SolutionResult(
            converged=False, iterations=0, max_mismatch=0.0,
            message="Network is not a connected radial tree.",
        )
    order, parent, children, branch_z = topo

    s_base_kw = network.base_mva * 1000.0
    p_net, q_load_net, b_shunt = _node_injections(network, s_base_kw)
    v_slack = complex(slack.v_set_pu if slack.v_set_pu is not None else 1.0, 0.0)

    pinned = {
        b.id: b.v_set_pu
        for b in network.buses
        if b.v_set_pu is not None and not b.is_slack
    }
    x_th = _thevenin_reactance(pinned, parent, branch_z)

    # Outer Q-compensation loop. With no pinned buses this runs exactly once.
    q_inject: dict[str, float] = {bus: 0.0 for bus in pinned}
    voltages: dict[str, complex] = {}
    inner_iters = 0
    inner_mismatch = 0.0
    inner_ok = False
    outer_ok = True

    for _ in range(_MAX_OUTER_ITER):
        q_net = dict(q_load_net)
        for bus, q in q_inject.items():
            q_net[bus] = q_load_net[bus] - q  # injected reactive lowers drawn Q

        voltages, inner_iters, inner_mismatch, inner_ok = _inner_sweep(
            order, parent, children, branch_z,
            p_net, q_net, b_shunt, v_slack, tol, max_iter,
        )
        if not inner_ok:
            outer_ok = False
            break
        if not pinned:
            break

        outer_ok = True
        for bus, v_set in pinned.items():
            dv = v_set - abs(voltages[bus])
            if abs(dv) > tol:
                outer_ok = False
            xth = x_th[bus]
            if xth > 1e-12:
                q_inject[bus] += _OUTER_DAMPING * dv / xth
        if outer_ok:
            break

    bus_results = [
        _bus_solution(b.id, voltages.get(b.id, complex(float("nan"))))
        for b in network.buses
    ]
    converged = inner_ok and outer_ok
    message = (
        "Converged." if converged
        else "Did not converge within iteration limit."
    )
    return SolutionResult(
        converged=converged,
        iterations=inner_iters,
        max_mismatch=inner_mismatch,
        bus_results=bus_results,
        message=message,
    )


# --------------------------------------------------------------------------- #
# Topology
# --------------------------------------------------------------------------- #
def _build_topology(network: Network, root: str):
    """BFS the radial tree from the slack root.

    Returns (order, parent, children, branch_z) where order is breadth-first
    bus ids, parent[bus]/children[bus] describe the rooted tree, and
    branch_z[bus] is the series impedance of the line joining bus to its parent.
    Returns None if the graph is not a single connected tree.
    """
    adjacency: dict[str, list[tuple[str, complex]]] = defaultdict(list)
    for ln in network.lines:
        z = complex(ln.r_pu, ln.x_pu)
        adjacency[ln.from_bus].append((ln.to_bus, z))
        adjacency[ln.to_bus].append((ln.from_bus, z))

    order: list[str] = []
    parent: dict[str, str] = {}
    children: dict[str, list[str]] = defaultdict(list)
    branch_z: dict[str, complex] = {}
    visited = {root}
    queue: deque[str] = deque([root])
    while queue:
        u = queue.popleft()
        order.append(u)
        for v, z in adjacency[u]:
            if v not in visited:
                visited.add(v)
                parent[v] = u
                branch_z[v] = z
                children[u].append(v)
                queue.append(v)

    if len(visited) != len(network.buses):
        return None
    return order, parent, children, branch_z


def _thevenin_reactance(pinned, parent, branch_z) -> dict[str, float]:
    """Sum of series reactance along the path from slack root to each pinned bus."""
    x_th: dict[str, float] = {}
    for bus in pinned:
        x = 0.0
        node = bus
        while node in parent:
            x += branch_z[node].imag
            node = parent[node]
        x_th[bus] = x
    return x_th


# --------------------------------------------------------------------------- #
# Injections (per-unit, load convention: positive = drawn from network)
# --------------------------------------------------------------------------- #
def _node_injections(network: Network, s_base_kw: float):
    p_net: dict[str, float] = {b.id: 0.0 for b in network.buses}
    q_net: dict[str, float] = {b.id: 0.0 for b in network.buses}
    b_shunt: dict[str, float] = {b.id: 0.0 for b in network.buses}

    for load in network.loads:
        p_net[load.bus] += load.p_kw / s_base_kw
        q_net[load.bus] += load.q_kvar / s_base_kw
    for gen in network.generators:
        p_net[gen.bus] -= gen.p_kw / s_base_kw
        q_net[gen.bus] -= gen.q_kvar / s_base_kw
    for cap in network.capacitors:
        if cap.in_service:
            # Rated kvar at 1 pu -> susceptance B; injects Q = B|V|^2.
            b_shunt[cap.bus] += cap.q_kvar / s_base_kw
    for ln in network.lines:
        half = ln.b_pu / 2.0
        b_shunt[ln.from_bus] += half
        b_shunt[ln.to_bus] += half
    return p_net, q_net, b_shunt


# --------------------------------------------------------------------------- #
# Inner backward-forward sweep
# --------------------------------------------------------------------------- #
def _inner_sweep(
    order, parent, children, branch_z,
    p_net, q_net, b_shunt, v_slack, tol, max_iter,
):
    slack = order[0]
    voltages: dict[str, complex] = {bus: complex(abs(v_slack), 0.0) for bus in order}
    voltages[slack] = v_slack

    converged = False
    iterations = 0
    max_dv = 0.0
    for iterations in range(1, max_iter + 1):
        prev = dict(voltages)

        # Backward sweep: node current then accumulate up the tree.
        i_branch: dict[str, complex] = {}
        node_current: dict[str, complex] = {}
        for bus in order:
            v = voltages[bus]
            s = complex(p_net[bus], q_net[bus])
            # Shunt current drawn from the node is Y·V = jB·V (B>0 capacitive),
            # so it supplies reactive power and lifts the downstream voltage.
            node_current[bus] = (s / v).conjugate() + 1j * b_shunt[bus] * v

        for bus in reversed(order):
            total = node_current[bus]
            for ch in children[bus]:
                total += i_branch[ch]
            i_branch[bus] = total

        # Forward sweep: propagate voltages from root outward.
        for bus in order:
            if bus == slack:
                continue
            voltages[bus] = voltages[parent[bus]] - branch_z[bus] * i_branch[bus]

        max_dv = max(abs(voltages[b] - prev[b]) for b in order)
        if max_dv < tol:
            converged = True
            break

    return voltages, iterations, max_dv, converged


# --------------------------------------------------------------------------- #
# Result formatting
# --------------------------------------------------------------------------- #
def _bus_solution(bus_id: str, v: complex) -> BusSolution:
    mag = abs(v)
    if math.isnan(mag):
        return BusSolution(bus_id=bus_id, v_pu=float("nan"), angle_deg=float("nan"))
    angle = math.degrees(cmath.phase(v))
    if mag < V_MIN_PU:
        violation = "under"
    elif mag > V_MAX_PU:
        violation = "over"
    else:
        violation = "ok"
    return BusSolution(bus_id=bus_id, v_pu=mag, angle_deg=angle, violation=violation)
