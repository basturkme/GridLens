"""VA (power-summation backward-forward sweep) power-flow solver for radial
distribution networks.

The "VA approach" is the volt-ampere (power) summation variant of the
backward-forward sweep: the backward pass accumulates the complex *power* flowing
in each branch rather than the current. The radial topology lets us avoid
building/inverting a Y-bus — we order buses by depth from the slack root, then
alternate two sweeps until the bus voltages stop moving.

  1. Order buses by depth from the slack root (BFS traversal of the radial tree).
  2. **Backward sweep (VA / power summation)** — from leaves toward root,
     accumulate the complex power (volt-amperes) flowing into each branch:
       S_branch = S_drawn + Σ_children (S_child + Z·|S_child|²/|V_child|²)
     where S_drawn = (P_load − P_gen) + j(Q_load − Q_gen) − jB_shunt·|V|²
     (capacitors / line charging enter as shunt susceptance, B>0 capacitive →
     supplies reactive power) and the Z·|S|²/|V|² term is the branch series loss
     (power, unlike current, is not conserved across a branch impedance).
  3. **Forward sweep** — from root toward leaves, recover the branch current from
     its VA flow and update voltages:
       I_branch = conj(S_branch / V_to);  V_to = V_from − Z_branch · I_branch
  4. Repeat until max|V_k − V_{k-1}| < tol or iter > max_iter.

  Current and power summation are algebraically equivalent for a radial feeder
  (I = (S/V)*), so this converges to the same bus voltages and angles; the VA
  form is used to match the project's required solver approach.

Operator-pinned leaf voltage (Bus.v_set_pu):
  Plain BFS converges with PQ buses + a single slack at a known voltage. When the
  operator instead pins a *leaf* voltage, the boundary condition flips: the leaf
  voltage is the known quantity and the slack/grid voltage becomes the unknown.
  An outer loop solves for it:
    a) Run the inner sweep with the current slack-voltage guess (all PQ).
    b) Read the resulting pinned-leaf |V| and compute ΔV = V_set − |V|.
    c) Scale the slack voltage toward the set-point: V_slack ·= V_set / |V_leaf|.
    d) Repeat until |ΔV| < tol.
  No reactive power is injected — holding the leaf simply determines what the
  source voltage must be (the slack voltage changes; everything else follows).
  Generators in this model are pure PQ injections (no regulated |V|).

Capacitor banks are modeled as shunt susceptances toggled by `in_service`.
"""
from __future__ import annotations

import cmath
import math
from collections import defaultdict, deque

from gridlens.core.models import BusSolution, Network, SolutionResult, SweepStep
from gridlens.utils.constants import (
    DEFAULT_MAX_ITER,
    DEFAULT_TOLERANCE_PU,
    V_MAX_PU,
    V_MIN_PU,
)

_MAX_OUTER_ITER = 40
_OUTER_DAMPING = 0.8

# Divergence guards: a radial sweep that runs away (a bus voltage collapsing to
# zero or blowing up) means the operating point is beyond the feeder's
# loadability. Detect it and report non-convergence instead of raising.
_MIN_VOLTAGE = 1e-9
_MAX_VOLTAGE = 1e3  # any per-unit voltage this large means the sweep is running away


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

    # Outer loop. When a leaf voltage is pinned, the operator fixes that leaf and
    # the slack/grid voltage becomes the unknown: we hold the pinned leaf at its
    # set-point and let the slack voltage take whatever value the radial drop
    # requires. (Per the course clarification — "fix the leaf, the source voltage
    # changes" — no reactive power is injected to do this.) With no pinned leaf
    # this runs exactly once with the slack fixed at its nominal voltage.
    v_mag = abs(v_slack)                  # slack voltage magnitude (solved for if pinned)
    ctrl_bus = next(iter(pinned), None)   # the leaf whose set-point drives the slack
    voltages: dict[str, complex] = {}
    inner_iters = 0
    inner_mismatch = 0.0
    inner_ok = False
    inner_reason = ""
    outer_ok = True
    mismatch_hist = []
    steps: list[SweepStep] = []
    outer_idx = 0
    # ``max_iter`` is a *total* sweep budget shared across every outer pass, so the
    # iteration count the user sees never exceeds the configured limit even when a
    # pinned leaf needs several slack-voltage adjustment passes.
    budget = max_iter

    for _ in range(_MAX_OUTER_ITER):
        if budget <= 0:
            outer_ok = False
            break
        outer_idx += 1
        voltages, inner_iters, inner_mismatch, inner_ok, inner_reason, mismatch_hist = _converge_inner(
            order, parent, children, branch_z,
            p_net, q_load_net, b_shunt, complex(v_mag, 0.0), tol, budget,
        )
        budget -= inner_iters
        # Record this pass's inner sweep as part of the full trajectory.
        for j, dv_inner in enumerate(mismatch_hist, start=1):
            steps.append(SweepStep(outer=outer_idx, inner=j, max_dv=dv_inner))
        if not inner_ok:
            outer_ok = False
            break
        if not pinned:
            break

        # Hold the pinned leaf by scaling the slack voltage toward the set-point.
        pinned_err = max(abs(v_set - abs(voltages[bus])) for bus, v_set in pinned.items())
        if steps:
            steps[-1].pinned_err = pinned_err
        if pinned_err < tol:
            outer_ok = True
            break
        outer_ok = False
        v_leaf = abs(voltages[ctrl_bus])
        if v_leaf > _MIN_VOLTAGE:
            ratio = pinned[ctrl_bus] / v_leaf
            v_mag *= 1.0 + _OUTER_DAMPING * (ratio - 1.0)

    bus_results = [
        _bus_solution(b.id, voltages.get(b.id, complex(float("nan"))))
        for b in network.buses
    ]
    converged = inner_ok and outer_ok
    if converged:
        message = "Converged."
        if pinned:
            message += (
                f"  Grid (slack) voltage settled at {v_mag:.4f} pu to hold the "
                "pinned leaf at its set-point."
            )
    elif not inner_ok:
        if inner_reason == "diverged":
            message = (
                "Solver diverged — the operating point may be beyond the "
                "feeder's loadability (check loads, generation, or the pinned "
                "leaf voltage)."
            )
        else:
            message = "Did not converge within the iteration limit."
    else:
        message = (
            "Pinned leaf voltage could not be held within tolerance; showing "
            "the closest result."
        )
    return SolutionResult(
        converged=converged,
        iterations=inner_iters,
        max_mismatch=inner_mismatch,
        bus_results=bus_results,
        message=message,
        mismatch_history=mismatch_hist,
        steps=steps,
        outer_iterations=outer_idx,
        # No reactive power is injected to hold the leaf now (the slack voltage is
        # adjusted instead), so there is no required-Q figure to report.
        pinned_q_inject_kvar={},
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
# Under-relaxation schedule. A plain sweep (damping 1.0) converges fast for
# well-conditioned feeders, but stiff cases — a shunt behind a large series
# impedance, as in low-voltage feeders with ohmic data — can make the fixed-point
# iteration overshoot and diverge. When that happens we retry with progressively
# heavier damping, which shrinks the iteration gain below 1 without moving the
# fixed point (the converged voltages are identical).
_DAMPING_SCHEDULE = (1.0, 0.5, 0.25, 0.1, 0.05)


def _converge_inner(
    order, parent, children, branch_z,
    p_net, q_net, b_shunt, v_slack, tol, max_iter,
):
    """Run the inner sweep, falling back to heavier under-relaxation if it does
    not converge. Returns the first converged result, or the last attempt.

    ``max_iter`` is honoured as a hard per-attempt cap: every damping level gets
    the same iteration budget the user configured, so the reported iteration
    count never exceeds it. If a genuinely stiff network needs more, the operator
    raises Max iterations — the solver does not silently overrun the setting."""
    result = None
    for damping in _DAMPING_SCHEDULE:
        result = _inner_sweep(
            order, parent, children, branch_z,
            p_net, q_net, b_shunt, v_slack, tol, max_iter, damping,
        )
        if result[3]:  # converged
            return result
    return result


def _inner_sweep(
    order, parent, children, branch_z,
    p_net, q_net, b_shunt, v_slack, tol, max_iter, damping=1.0,
):
    slack = order[0]
    voltages: dict[str, complex] = {bus: complex(abs(v_slack), 0.0) for bus in order}
    voltages[slack] = v_slack

    converged = False
    iterations = 0
    max_dv = 0.0
    mismatch_history = []
    for iterations in range(1, max_iter + 1):
        prev = dict(voltages)

        # Bail out before dividing by a collapsed / runaway voltage.
        for bus in order:
            mag = abs(voltages[bus])
            if not cmath.isfinite(voltages[bus]) or mag < _MIN_VOLTAGE or mag > _MAX_VOLTAGE:
                return voltages, iterations, float("inf"), False, "diverged", mismatch_history

        # Backward sweep (VA / power summation): from leaves to root, accumulate
        # the complex power (volt-amperes) flowing into each branch — the local
        # drawn power plus every downstream branch power *and its series loss*.
        # Losses are explicit here because, unlike current, power is not conserved
        # across a branch impedance.
        s_branch: dict[str, complex] = {}
        for bus in reversed(order):
            v = voltages[bus]
            # Local power drawn from upstream: load − generation, minus the
            # reactive power a shunt (capacitor B>0 / line charging) supplies,
            # S_shunt = −jB|V|² (B>0 capacitive → injects Q, lifts the voltage).
            s_drawn = complex(p_net[bus], q_net[bus]) - 1j * b_shunt[bus] * (abs(v) ** 2)
            total = s_drawn
            for ch in children[bus]:
                s_ch = s_branch[ch]
                loss = branch_z[ch] * (abs(s_ch) ** 2) / (abs(voltages[ch]) ** 2)
                total += s_ch + loss
            s_branch[bus] = total

        # Forward sweep: propagate voltages from root outward, recovering each
        # branch current from its VA flow, I_branch = conj(S_branch / V_to).
        # Under-relaxation (damping < 1) blends the new estimate with the old to
        # keep stiff cases stable; it does not change the converged fixed point.
        for bus in order:
            if bus == slack:
                continue
            i_branch = (s_branch[bus] / voltages[bus]).conjugate()
            target = voltages[parent[bus]] - branch_z[bus] * i_branch
            voltages[bus] = voltages[bus] + damping * (target - voltages[bus])

        max_dv = max(abs(voltages[b] - prev[b]) for b in order)
        mismatch_history.append(max_dv)
        if not math.isfinite(max_dv):
            return voltages, iterations, float("inf"), False, "diverged", mismatch_history
        if max_dv < tol:
            converged = True
            break

    return voltages, iterations, max_dv, converged, ("" if converged else "iterations"), mismatch_history


# --------------------------------------------------------------------------- #
# Result formatting
# --------------------------------------------------------------------------- #
def _bus_solution(bus_id: str, v: complex) -> BusSolution:
    mag = abs(v)
    if not math.isfinite(mag):
        return BusSolution(bus_id=bus_id, v_pu=float("nan"), angle_deg=float("nan"))
    angle = math.degrees(cmath.phase(v))
    if mag < V_MIN_PU:
        violation = "under"
    elif mag > V_MAX_PU:
        violation = "over"
    else:
        violation = "ok"
    return BusSolution(bus_id=bus_id, v_pu=mag, angle_deg=angle, violation=violation)
