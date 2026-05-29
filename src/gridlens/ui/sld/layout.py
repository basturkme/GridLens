"""Radial tree layout for the single-line diagram.

Buses are placed in columns by their depth from the slack root (left → right,
matching the feeder flow in the project's Figure 1) and in rows by a simple
tidy-tree pass: each leaf takes the next row, each internal bus centres on its
children. Good enough — and stable — for the ≤10-bus networks this tool targets.
"""
from __future__ import annotations

from collections import defaultdict, deque

from PyQt6.QtCore import QPointF

from gridlens.core.models import Network

COL_DX = 180.0  # horizontal spacing between depth columns
ROW_DY = 120.0  # vertical spacing between rows


def radial_layout(network: Network) -> dict[str, QPointF]:
    """Return a scene position for every bus id."""
    if not network.buses:
        return {}

    slack = next((b for b in network.buses if b.is_slack), network.buses[0])

    adjacency: dict[str, list[str]] = defaultdict(list)
    for ln in network.lines:
        adjacency[ln.from_bus].append(ln.to_bus)
        adjacency[ln.to_bus].append(ln.from_bus)

    parent: dict[str, str] = {}
    children: dict[str, list[str]] = defaultdict(list)
    depth: dict[str, int] = {slack.id: 0}
    order: list[str] = []
    visited = {slack.id}
    queue: deque[str] = deque([slack.id])
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in sorted(adjacency[u]):
            if v not in visited:
                visited.add(v)
                parent[v] = u
                children[u].append(v)
                depth[v] = depth[u] + 1
                queue.append(v)

    # Assign rows: leaves consume successive rows; parents centre on children.
    row = [0]
    y_row: dict[str, float] = {}

    def assign(node: str) -> None:
        kids = children[node]
        if not kids:
            y_row[node] = float(row[0])
            row[0] += 1
            return
        for kid in kids:
            assign(kid)
        y_row[node] = sum(y_row[k] for k in kids) / len(kids)

    assign(slack.id)

    pos: dict[str, QPointF] = {}
    for bus in network.buses:
        if bus.id in depth:
            pos[bus.id] = QPointF(depth[bus.id] * COL_DX, y_row[bus.id] * ROW_DY)
        else:
            # Disconnected bus (shouldn't happen for a validated network): stack it
            # below everything so it's still visible rather than silently dropped.
            pos[bus.id] = QPointF(0.0, row[0] * ROW_DY)
            row[0] += 1
    return pos
