"""Network file parser.

Reads and writes the JSON intermediate format documented in data/FORMAT.md
and converts it to/from the :class:`~gridlens.core.models.Network` model. When
the course-provided file format spec arrives, add an adapter here that converts
it into the same model — the solver and UI are unaffected.

Validation is split in two:

* structural shape / types  -> raised eagerly while parsing (``_from_dict``)
* network-level invariants  -> :func:`validate_network` (radial tree, single
  slack, ≤10 buses, unique ids, dangling references)

Both surface as :class:`ParserError` so callers have a single thing to catch.
"""
from __future__ import annotations

import json
from pathlib import Path

from gridlens.core.models import (
    Bus,
    Capacitor,
    Generator,
    Line,
    Load,
    Network,
)
from gridlens.utils.constants import MAX_BUSES


class ParserError(ValueError):
    """Raised when a network file is malformed or violates a constraint."""


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def load_network(path: str | Path) -> Network:
    """Load and validate a network from a JSON file."""
    path = Path(path)
    if not path.exists():
        raise ParserError(f"File not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ParserError(f"Invalid JSON in {path.name}: {e}") from e
    network = _from_dict(data)
    validate_network(network)
    return network


def save_network(network: Network, path: str | Path) -> None:
    """Serialize a network to JSON. The output round-trips through
    :func:`load_network` without loss."""
    path = Path(path)
    text = json.dumps(_to_dict(network), indent=2, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")


def validate_network(network: Network) -> None:
    """Check the network-level invariants from data/FORMAT.md.

    Raises :class:`ParserError` on the first violation found.
    """
    buses = network.buses
    if not buses:
        raise ParserError("Network has no buses.")
    if len(buses) > MAX_BUSES:
        raise ParserError(
            f"Network has {len(buses)} buses; the maximum supported is {MAX_BUSES}."
        )

    bus_ids = [b.id for b in buses]
    _ensure_unique(bus_ids, "bus")
    bus_id_set = set(bus_ids)

    _ensure_unique([ln.id for ln in network.lines], "line")
    _ensure_unique([x.id for x in network.loads], "load")
    _ensure_unique([x.id for x in network.generators], "generator")
    _ensure_unique([x.id for x in network.capacitors], "capacitor")

    # Exactly one slack/source bus.
    slacks = [b.id for b in buses if b.is_slack]
    if len(slacks) == 0:
        raise ParserError("No slack bus defined (exactly one bus needs is_slack: true).")
    if len(slacks) > 1:
        raise ParserError(f"Multiple slack buses defined: {', '.join(slacks)}.")

    # Pinned voltage only makes sense on leaf buses.
    for b in buses:
        if b.v_set_pu is not None and not b.is_leaf:
            raise ParserError(
                f"Bus '{b.id}' has v_set_pu but is not a leaf (is_leaf: false)."
            )

    # Every reference must resolve to a real bus.
    for ln in network.lines:
        for endpoint in (ln.from_bus, ln.to_bus):
            if endpoint not in bus_id_set:
                raise ParserError(
                    f"Line '{ln.id}' references unknown bus '{endpoint}'."
                )
        if ln.from_bus == ln.to_bus:
            raise ParserError(f"Line '{ln.id}' connects bus '{ln.from_bus}' to itself.")

    for kind, items in (
        ("load", network.loads),
        ("generator", network.generators),
        ("capacitor", network.capacitors),
    ):
        for item in items:
            if item.bus not in bus_id_set:
                raise ParserError(
                    f"{kind.capitalize()} '{item.id}' references unknown bus '{item.bus}'."
                )

    _ensure_radial_tree(network, bus_id_set)


# --------------------------------------------------------------------------- #
# Deserialization
# --------------------------------------------------------------------------- #
def _from_dict(data: object) -> Network:
    if not isinstance(data, dict):
        raise ParserError("Top-level network data must be a JSON object.")

    network = Network(
        name=_opt_str(data, "name", "") or "",
        base_mva=_opt_num(data, "base_mva", 1.0),
    )
    network.buses = [_bus_from_dict(d, i) for i, d in enumerate(_seq(data, "buses"))]
    network.lines = [_line_from_dict(d, i) for i, d in enumerate(_seq(data, "lines"))]
    network.loads = [
        _injection_from_dict(Load, "load", d, i)
        for i, d in enumerate(_seq(data, "loads"))
    ]
    network.generators = [
        _injection_from_dict(Generator, "generator", d, i)
        for i, d in enumerate(_seq(data, "generators"))
    ]
    network.capacitors = [
        _capacitor_from_dict(d, i) for i, d in enumerate(_seq(data, "capacitors"))
    ]
    return network


def _bus_from_dict(d: object, index: int) -> Bus:
    ctx = f"bus #{index + 1}"
    obj = _as_obj(d, ctx)
    return Bus(
        id=_req_str(obj, "id", ctx),
        name=_opt_str(obj, "name", ""),
        base_kv=_opt_num(obj, "base_kv", 1.0),
        is_slack=_opt_bool(obj, "is_slack", False),
        is_leaf=_opt_bool(obj, "is_leaf", False),
        v_set_pu=_opt_num_or_none(obj, "v_set_pu"),
    )


def _line_from_dict(d: object, index: int) -> Line:
    ctx = f"line #{index + 1}"
    obj = _as_obj(d, ctx)
    return Line(
        id=_req_str(obj, "id", ctx),
        from_bus=_req_str(obj, "from_bus", ctx),
        to_bus=_req_str(obj, "to_bus", ctx),
        r_pu=_opt_num(obj, "r_pu", 0.0),
        x_pu=_opt_num(obj, "x_pu", 0.0),
        b_pu=_opt_num(obj, "b_pu", 0.0),
        rating_a=_opt_num_or_none(obj, "rating_a"),
    )


def _injection_from_dict(cls, kind: str, d: object, index: int):
    ctx = f"{kind} #{index + 1}"
    obj = _as_obj(d, ctx)
    return cls(
        id=_req_str(obj, "id", ctx),
        bus=_req_str(obj, "bus", ctx),
        p_kw=_opt_num(obj, "p_kw", 0.0),
        q_kvar=_opt_num(obj, "q_kvar", 0.0),
    )


def _capacitor_from_dict(d: object, index: int) -> Capacitor:
    ctx = f"capacitor #{index + 1}"
    obj = _as_obj(d, ctx)
    return Capacitor(
        id=_req_str(obj, "id", ctx),
        bus=_req_str(obj, "bus", ctx),
        q_kvar=_opt_num(obj, "q_kvar", 0.0),
        in_service=_opt_bool(obj, "in_service", True),
    )


# --------------------------------------------------------------------------- #
# Serialization
# --------------------------------------------------------------------------- #
def _to_dict(network: Network) -> dict:
    return {
        "name": network.name,
        "base_mva": network.base_mva,
        "buses": [_bus_to_dict(b) for b in network.buses],
        "lines": [_line_to_dict(ln) for ln in network.lines],
        "loads": [_injection_to_dict(x) for x in network.loads],
        "generators": [_injection_to_dict(x) for x in network.generators],
        "capacitors": [_capacitor_to_dict(c) for c in network.capacitors],
    }


def _bus_to_dict(b: Bus) -> dict:
    out: dict = {
        "id": b.id,
        "name": b.name,
        "base_kv": b.base_kv,
        "is_slack": b.is_slack,
        "is_leaf": b.is_leaf,
    }
    if b.v_set_pu is not None:
        out["v_set_pu"] = b.v_set_pu
    return out


def _line_to_dict(ln: Line) -> dict:
    out: dict = {
        "id": ln.id,
        "from_bus": ln.from_bus,
        "to_bus": ln.to_bus,
        "r_pu": ln.r_pu,
        "x_pu": ln.x_pu,
        "b_pu": ln.b_pu,
    }
    if ln.rating_a is not None:
        out["rating_a"] = ln.rating_a
    return out


def _injection_to_dict(x) -> dict:
    return {"id": x.id, "bus": x.bus, "p_kw": x.p_kw, "q_kvar": x.q_kvar}


def _capacitor_to_dict(c: Capacitor) -> dict:
    return {"id": c.id, "bus": c.bus, "q_kvar": c.q_kvar, "in_service": c.in_service}


# --------------------------------------------------------------------------- #
# Field helpers
# --------------------------------------------------------------------------- #
def _seq(data: dict, key: str) -> list:
    value = data.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list):
        raise ParserError(f"'{key}' must be a list.")
    return value


def _as_obj(d: object, ctx: str) -> dict:
    if not isinstance(d, dict):
        raise ParserError(f"{ctx} must be a JSON object.")
    return d


def _req_str(obj: dict, key: str, ctx: str) -> str:
    if key not in obj:
        raise ParserError(f"{ctx} is missing required field '{key}'.")
    value = obj[key]
    if not isinstance(value, str) or not value:
        raise ParserError(f"{ctx} field '{key}' must be a non-empty string.")
    return value


def _opt_str(obj: dict, key: str, default: str) -> str:
    value = obj.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ParserError(f"Field '{key}' must be a string.")
    return value


def _opt_num(obj: dict, key: str, default: float) -> float:
    if key not in obj or obj[key] is None:
        return default
    return _coerce_num(obj[key], key)


def _opt_num_or_none(obj: dict, key: str) -> float | None:
    if key not in obj or obj[key] is None:
        return None
    return _coerce_num(obj[key], key)


def _coerce_num(value: object, key: str) -> float:
    # bool is a subclass of int — reject it so True doesn't silently become 1.0.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ParserError(f"Field '{key}' must be a number, got {value!r}.")
    return float(value)


def _opt_bool(obj: dict, key: str, default: bool) -> bool:
    value = obj.get(key, default)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ParserError(f"Field '{key}' must be a boolean (true/false).")
    return value


def _ensure_unique(ids: list[str], kind: str) -> None:
    seen: set[str] = set()
    for i in ids:
        if i in seen:
            raise ParserError(f"Duplicate {kind} id: '{i}'.")
        seen.add(i)


def _ensure_radial_tree(network: Network, bus_ids: set[str]) -> None:
    """A valid radial feeder is a connected, acyclic, undirected graph: it must
    have exactly (buses - 1) lines and be fully connected from the slack bus."""
    n_buses = len(bus_ids)
    n_lines = len(network.lines)
    if n_lines != n_buses - 1:
        raise ParserError(
            f"Network is not radial: {n_buses} buses need exactly "
            f"{n_buses - 1} lines, but found {n_lines} "
            "(a radial feeder is a tree)."
        )

    adjacency: dict[str, list[str]] = {b: [] for b in bus_ids}
    for ln in network.lines:
        adjacency[ln.from_bus].append(ln.to_bus)
        adjacency[ln.to_bus].append(ln.from_bus)

    root = next(b.id for b in network.buses if b.is_slack)
    visited: set[str] = set()
    stack = [root]
    while stack:
        node = stack.pop()
        if node in visited:
            continue
        visited.add(node)
        stack.extend(adjacency[node])

    if len(visited) != n_buses:
        unreachable = sorted(bus_ids - visited)
        raise ParserError(
            "Network is not connected (radial feeder must be a single tree); "
            f"buses unreachable from slack '{root}': {', '.join(unreachable)}."
        )
