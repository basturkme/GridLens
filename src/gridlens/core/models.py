"""Network domain model.

Pure dataclasses — no Qt imports. Solver and parser operate on these types.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Bus:
    id: str
    name: str = ""
    base_kv: float = 1.0
    is_slack: bool = False
    is_leaf: bool = False
    v_set_pu: float | None = None  # operator-pinned magnitude (leaf override)


@dataclass
class Line:
    id: str
    from_bus: str
    to_bus: str
    r_pu: float = 0.0
    x_pu: float = 0.0
    b_pu: float = 0.0
    rating_a: float | None = None
    # A transformer is modelled as a branch too (it joins two buses and carries a
    # series reactance). When ``is_transformer`` is set, ``r_pu``/``x_pu`` already
    # hold the impedance on the *system* base so the solver treats it like any
    # other branch; the ``xfmr_*`` fields keep the nameplate data for round-trip
    # save back to the course file format. ``from_bus`` is the HV side.
    is_transformer: bool = False
    xfmr_rated_mva: float | None = None
    xfmr_hv_kv: float | None = None
    xfmr_lv_kv: float | None = None
    xfmr_x_pu: float | None = None  # reactance on the transformer's own MVA base


@dataclass
class Load:
    id: str
    bus: str
    p_kw: float = 0.0
    q_kvar: float = 0.0
    s_rated_mva: float = 0.0  # nameplate apparent power (operating P/Q set by hand)


@dataclass
class Generator:
    id: str
    bus: str
    p_kw: float = 0.0
    q_kvar: float = 0.0
    s_rated_mva: float = 0.0  # nameplate apparent power (operating P/Q set by hand)


@dataclass
class Capacitor:
    id: str
    bus: str
    q_kvar: float = 0.0
    in_service: bool = True


@dataclass
class Network:
    name: str = ""
    base_mva: float = 1.0
    buses: list[Bus] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    loads: list[Load] = field(default_factory=list)
    generators: list[Generator] = field(default_factory=list)
    capacitors: list[Capacitor] = field(default_factory=list)


@dataclass
class BusSolution:
    bus_id: str
    v_pu: float
    angle_deg: float
    violation: str = "ok"  # "ok" | "under" | "over"


@dataclass
class SweepStep:
    """One inner backward-forward sweep iteration, tagged with the outer
    Q-compensation pass it belongs to.

    ``pinned_err`` is the worst pinned-bus voltage error (|v_set - |V||) measured
    at the *end* of an outer pass; it is None for inner iterations that are not a
    pass boundary and for networks without voltage-controlled (pinned) buses.
    """

    outer: int
    inner: int
    max_dv: float
    pinned_err: float | None = None


@dataclass
class SolutionResult:
    converged: bool
    iterations: int
    max_mismatch: float
    bus_results: list[BusSolution] = field(default_factory=list)
    message: str = ""
    mismatch_history: list[float] = field(default_factory=list)
    # Full solve trajectory across every outer Q-compensation pass (the table on
    # the Solver page renders this); ``mismatch_history`` above stays as the inner
    # history of the final pass for backwards compatibility.
    steps: list[SweepStep] = field(default_factory=list)
    outer_iterations: int = 1
    # Reactive power (kvar) the outer loop had to inject at each pinned bus to
    # hold its target |V| — i.e. the reactive support that sizing a capacitor /
    # SVC there would need to provide. Empty when no bus is voltage-pinned.
    pinned_q_inject_kvar: dict[str, float] = field(default_factory=dict)
