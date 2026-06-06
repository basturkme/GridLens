"""Network file parser.

The on-disk format is the course-provided JSON schema (see ``data/FORMAT.md``):
``system_data`` / ``bus_data`` / ``load_data`` / ``gen_data`` / ``shunt_data`` /
``line_data`` / ``transformer_data``. :func:`load_network` reads it into the
internal :class:`~gridlens.core.models.Network` model (the solver and UI operate
on that model, unaffected by the file shape) and :func:`save_network` writes it
back out in the same schema.

Key conversions the adapter performs:

* line impedances given in **ohms** → per-unit on the system base
  (``Z_base = kV² / S_base``, using the line's voltage level);
* a **transformer** becomes a branch too — its ``x_pu`` (on the transformer's own
  MVA base) is referred to the system base and the transformer is stored as a
  :class:`Line` flagged ``is_transformer`` (HV side = ``from_bus``);
* loads / generators carry only an ``s_rated_mva`` nameplate in the course files;
  the **operating point** (P, Q — and hence power factor) is entered by hand, so
  it defaults to zero on load unless the file also carries ``p_mw`` / ``q_mvar``
  (which our own saved files do, so edits round-trip). Power factor is never
  assumed.
* leaf buses (where the operator may pin a voltage) are derived from the
  topology: a non-slack bus with a single branch.

A legacy intermediate format (top-level ``buses`` / ``lines`` arrays) is still
accepted on read for backwards compatibility.

Validation is split in two:

* structural shape / types  -> raised eagerly while parsing
* network-level invariants  -> :func:`validate_network` (radial tree, single
  slack, ≤ MAX_BUSES buses, unique ids, dangling references)

Both surface as :class:`ParserError` so callers have a single thing to catch.
"""
from __future__ import annotations

import json
from collections import defaultdict
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
    if not isinstance(data, dict):
        raise ParserError("Top-level network data must be a JSON object.")
    if _is_instructor_format(data):
        network = _from_instructor_dict(data)
    else:
        network = _from_dict(data)
    validate_network(network)
    return network


def save_network(network: Network, path: str | Path) -> None:
    """Serialize a network to JSON in the course file format. The output
    round-trips through :func:`load_network` without loss."""
    path = Path(path)
    text = json.dumps(_to_instructor_dict(network), indent=2, ensure_ascii=False)
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

    # Lines and transformers share the branch namespace (both live in
    # ``network.lines``); their ids must be unique together.
    _ensure_unique([ln.id for ln in network.lines], "branch")
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
                kind = "Transformer" if ln.is_transformer else "Line"
                raise ParserError(
                    f"{kind} '{ln.id}' references unknown bus '{endpoint}'."
                )
        if ln.from_bus == ln.to_bus:
            raise ParserError(f"Branch '{ln.id}' connects bus '{ln.from_bus}' to itself.")

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
# Instructor (course) format
# --------------------------------------------------------------------------- #
def _is_instructor_format(data: dict) -> bool:
    return any(
        k in data
        for k in ("system_data", "bus_data", "line_data", "transformer_data")
    )


def _from_instructor_dict(data: dict) -> Network:
    system = _seq(data, "system_data")
    sys0 = _as_obj(system[0], "system_data[0]") if system else {}
    name = _opt_str(sys0, "network_name", "") or ""
    base_mva = _opt_num(sys0, "s_base_mva", 1.0)
    slack_id = _opt_id(sys0, "slack_bus")

    network = Network(name=name, base_mva=base_mva)

    bus_kv: dict[str, float] = {}
    for i, d in enumerate(_seq(data, "bus_data")):
        ctx = f"bus #{i + 1}"
        obj = _as_obj(d, ctx)
        bid = _req_id(obj, "bus_id", ctx)
        kv = _opt_num(obj, "voltage_level_kv", 1.0)
        bus_kv[bid] = kv
        network.buses.append(
            Bus(
                id=bid,
                name=_opt_str(obj, "bus_name", ""),
                base_kv=kv,
                is_slack=(slack_id is not None and bid == slack_id),
                is_leaf=False,  # derived from topology below
                v_set_pu=_opt_num_or_none(obj, "v_set_pu"),
            )
        )

    # Lines: impedance given in ohms, referred to per-unit on the system base.
    for i, d in enumerate(_seq(data, "line_data")):
        ctx = f"line #{i + 1}"
        obj = _as_obj(d, ctx)
        fb = _req_id(obj, "from_bus_id", ctx)
        tb = _req_id(obj, "to_bus_id", ctx)
        z_base = _z_base(bus_kv.get(fb, 1.0), base_mva)
        network.lines.append(
            Line(
                id=_req_id(obj, "line_id", ctx),
                from_bus=fb,
                to_bus=tb,
                r_pu=_opt_num(obj, "r_ohm", 0.0) / z_base,
                x_pu=_opt_num(obj, "x_ohm", 0.0) / z_base,
                b_pu=0.0,
            )
        )

    # Transformers: a branch with its reactance referred to the system base. The
    # internal id is "T"-prefixed so it never collides with a line id.
    for i, d in enumerate(_seq(data, "transformer_data")):
        ctx = f"transformer #{i + 1}"
        obj = _as_obj(d, ctx)
        hv = _req_id(obj, "hv_bus_id", ctx)
        lv = _req_id(obj, "lv_bus_id", ctx)
        rated = _opt_num(obj, "rated_s_mva", base_mva)
        x_own = _opt_num(obj, "x_pu", 0.0)
        x_sys = x_own * (base_mva / rated) if rated else x_own
        network.lines.append(
            Line(
                id="T" + _req_id(obj, "transformer_id", ctx),
                from_bus=hv,
                to_bus=lv,
                r_pu=0.0,
                x_pu=x_sys,
                b_pu=0.0,
                is_transformer=True,
                xfmr_rated_mva=rated,
                xfmr_hv_kv=_opt_num_or_none(obj, "v_rated_high_kv"),
                xfmr_lv_kv=_opt_num_or_none(obj, "v_rated_low_kv"),
                xfmr_x_pu=x_own,
            )
        )

    for i, d in enumerate(_seq(data, "load_data")):
        ctx = f"load #{i + 1}"
        obj = _as_obj(d, ctx)
        network.loads.append(
            Load(
                id=_req_id(obj, "load_id", ctx),
                bus=_req_id(obj, "bus_id", ctx),
                p_kw=_opt_num(obj, "p_mw", 0.0) * 1000.0,
                q_kvar=_opt_num(obj, "q_mvar", 0.0) * 1000.0,
                s_rated_mva=_opt_num(obj, "s_rated_mva", 0.0),
            )
        )

    for i, d in enumerate(_seq(data, "gen_data")):
        ctx = f"generator #{i + 1}"
        obj = _as_obj(d, ctx)
        network.generators.append(
            Generator(
                # Spec uses `gen_id`; the course's own example file uses
                # `generator_id` — accept either so both parse.
                id=_req_id_any(obj, ("gen_id", "generator_id"), ctx),
                bus=_req_id(obj, "bus_id", ctx),
                p_kw=_opt_num(obj, "p_mw", 0.0) * 1000.0,
                q_kvar=_opt_num(obj, "q_mvar", 0.0) * 1000.0,
                s_rated_mva=_opt_num(obj, "s_rated_mva", 0.0),
            )
        )

    for i, d in enumerate(_seq(data, "shunt_data")):
        ctx = f"shunt #{i + 1}"
        obj = _as_obj(d, ctx)
        # Course sign convention: q_mvar > 0 absorbs reactive power (a reactor),
        # q_mvar < 0 supplies it (a capacitor). Our internal Capacitor.q_kvar is
        # the *supplied* reactive (B>0 capacitive), so flip the sign.
        network.capacitors.append(
            Capacitor(
                id=_req_id(obj, "shunt_id", ctx),
                bus=_req_id(obj, "bus_id", ctx),
                q_kvar=-_opt_num(obj, "q_mvar", 0.0) * 1000.0,
                in_service=_opt_bool(obj, "in_service", True),
            )
        )

    _mark_leaves(network)
    return network


def _to_instructor_dict(network: Network) -> dict:
    slack = next((b.id for b in network.buses if b.is_slack), None)
    system: dict = {"network_name": network.name, "s_base_mva": network.base_mva}
    if slack is not None:
        system["slack_bus"] = _id_out(slack)

    bus_kv = {b.id: b.base_kv for b in network.buses}
    bus_data = []
    for b in network.buses:
        entry: dict = {
            "bus_id": _id_out(b.id),
            "bus_name": b.name,
            "voltage_level_kv": b.base_kv,
        }
        if b.v_set_pu is not None:
            entry["v_set_pu"] = b.v_set_pu
        bus_data.append(entry)

    line_data = []
    transformer_data = []
    for ln in network.lines:
        if ln.is_transformer:
            transformer_data.append(
                {
                    "transformer_id": _id_out(_strip_t(ln.id)),
                    "hv_bus_id": _id_out(ln.from_bus),
                    "lv_bus_id": _id_out(ln.to_bus),
                    "v_rated_high_kv": ln.xfmr_hv_kv
                    if ln.xfmr_hv_kv is not None
                    else bus_kv.get(ln.from_bus),
                    "v_rated_low_kv": ln.xfmr_lv_kv
                    if ln.xfmr_lv_kv is not None
                    else bus_kv.get(ln.to_bus),
                    "rated_s_mva": ln.xfmr_rated_mva
                    if ln.xfmr_rated_mva is not None
                    else network.base_mva,
                    "x_pu": ln.xfmr_x_pu if ln.xfmr_x_pu is not None else ln.x_pu,
                }
            )
        else:
            z_base = _z_base(bus_kv.get(ln.from_bus, 1.0), network.base_mva)
            line_data.append(
                {
                    "line_id": _id_out(ln.id),
                    "from_bus_id": _id_out(ln.from_bus),
                    "to_bus_id": _id_out(ln.to_bus),
                    "r_ohm": ln.r_pu * z_base,
                    "x_ohm": ln.x_pu * z_base,
                }
            )

    load_data = [
        {
            "load_id": _id_out(x.id),
            "bus_id": _id_out(x.bus),
            "s_rated_mva": x.s_rated_mva,
            "p_mw": x.p_kw / 1000.0,
            "q_mvar": x.q_kvar / 1000.0,
        }
        for x in network.loads
    ]
    gen_data = [
        {
            "gen_id": _id_out(x.id),
            "bus_id": _id_out(x.bus),
            "s_rated_mva": x.s_rated_mva,
            "p_mw": x.p_kw / 1000.0,
            "q_mvar": x.q_kvar / 1000.0,
        }
        for x in network.generators
    ]
    shunt_data = [
        {
            "shunt_id": _id_out(x.id),
            "bus_id": _id_out(x.bus),
            "q_mvar": -x.q_kvar / 1000.0,  # supplied (internal) → absorbed (course)
            "in_service": x.in_service,
        }
        for x in network.capacitors
    ]

    return {
        "system_data": [system],
        "bus_data": bus_data,
        "load_data": load_data,
        "gen_data": gen_data,
        "shunt_data": shunt_data,
        "line_data": line_data,
        "transformer_data": transformer_data,
    }


def _z_base(kv: float, base_mva: float) -> float:
    z = (kv * kv) / base_mva if base_mva else 1.0
    return z if z else 1.0


def _mark_leaves(network: Network) -> None:
    """A leaf is a non-slack bus with exactly one incident branch."""
    degree: dict[str, int] = defaultdict(int)
    for ln in network.lines:
        degree[ln.from_bus] += 1
        degree[ln.to_bus] += 1
    for b in network.buses:
        if not b.is_slack and degree[b.id] == 1:
            b.is_leaf = True


def _strip_t(branch_id: str) -> str:
    return branch_id[1:] if branch_id.startswith("T") else branch_id


# --------------------------------------------------------------------------- #
# Legacy intermediate format (top-level buses / lines) — read only
# --------------------------------------------------------------------------- #
def _from_dict(data: dict) -> Network:
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


def _req_id(obj: dict, key: str, ctx: str) -> str:
    """An id field that may be given as an integer or a string; normalised to str."""
    if key not in obj or obj[key] is None:
        raise ParserError(f"{ctx} is missing required field '{key}'.")
    return _id_str(obj[key], key, ctx)


def _req_id_any(obj: dict, keys: tuple[str, ...], ctx: str) -> str:
    """Like :func:`_req_id` but accepts the first of several alias field names."""
    for key in keys:
        if key in obj and obj[key] is not None:
            return _id_str(obj[key], key, ctx)
    raise ParserError(f"{ctx} is missing required field '{keys[0]}'.")


def _opt_id(obj: dict, key: str) -> str | None:
    if key not in obj or obj[key] is None:
        return None
    return _id_str(obj[key], key, key)


def _id_str(value: object, key: str, ctx: str) -> str:
    if isinstance(value, bool):
        raise ParserError(f"{ctx} field '{key}' must be an id, got {value!r}.")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value:
        return value
    raise ParserError(f"{ctx} field '{key}' must be a non-empty id (string or integer).")


def _id_out(value: str):
    """Emit numeric ids as integers (matching the course format), others as-is."""
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)
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
    have exactly (buses - 1) branches (lines + transformers) and be fully
    connected from the slack bus."""
    n_buses = len(bus_ids)
    n_branches = len(network.lines)
    if n_branches != n_buses - 1:
        raise ParserError(
            f"Network is not radial: {n_buses} buses need exactly "
            f"{n_buses - 1} branches, but found {n_branches} "
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
