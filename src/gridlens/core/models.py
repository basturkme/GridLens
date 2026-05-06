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


@dataclass
class Load:
    id: str
    bus: str
    p_kw: float = 0.0
    q_kvar: float = 0.0


@dataclass
class Generator:
    id: str
    bus: str
    p_kw: float = 0.0
    q_kvar: float = 0.0


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
class SolutionResult:
    converged: bool
    iterations: int
    max_mismatch: float
    bus_results: list[BusSolution] = field(default_factory=list)
    message: str = ""
