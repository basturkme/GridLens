"""Network file parser.

Currently reads the JSON intermediate format documented in data/FORMAT.md.
When the course-provided file format spec arrives, add an adapter here that
converts it into the same Network model.
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


class ParserError(ValueError):
    """Raised when a network file is malformed."""


def load_network(path: str | Path) -> Network:
    path = Path(path)
    if not path.exists():
        raise ParserError(f"File not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ParserError(f"Invalid JSON in {path.name}: {e}") from e
    return _from_dict(data)


def _from_dict(data: dict) -> Network:
    raise NotImplementedError(
        "Parser implementation deferred to Sprint 1. "
        "See data/FORMAT.md for the target schema."
    )


def save_network(network: Network, path: str | Path) -> None:
    raise NotImplementedError("Serialization deferred to Sprint 1.")
