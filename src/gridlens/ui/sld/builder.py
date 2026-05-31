"""Assemble a QGraphicsScene from a Network (+ optional power-flow solution)."""
from __future__ import annotations

from collections import defaultdict

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtWidgets import QGraphicsScene

from gridlens.core.models import Network, SolutionResult
from gridlens.ui.sld.items import (
    BAR_WIDTH,
    BUS_HALF_H,
    BranchItem,
    BusItem,
    CapacitorItem,
    GeneratorItem,
    GridItem,
    LoadItem,
    TransformerItem,
)
from gridlens.ui.theme.colors import Colors

_EQUIP_GAP = 46.0  # vertical spacing of stacked equipment under a bus


def build_scene(
    scene: QGraphicsScene,
    network: Network | None,
    solution: SolutionResult | None = None,
) -> dict[str, BusItem]:
    """Clear ``scene`` and render ``network``. Returns the bus-id → BusItem map
    so the view can drive selection from elsewhere."""
    scene.clear()
    if network is None or not network.buses:
        placeholder = scene.addText(
            "SLD canvas — load a network to render the single-line diagram."
        )
        placeholder.setDefaultTextColor(Qt.GlobalColor.gray)
        return {}

    from gridlens.ui.sld.layout import radial_layout

    pos = radial_layout(network)
    bus_by_id = {b.id: b for b in network.buses}
    sol_by_bus = (
        {b.bus_id: b for b in solution.bus_results} if solution is not None else {}
    )

    # --- branches (drawn first so buses sit on top) --- #
    for ln in network.lines:
        if ln.from_bus not in pos or ln.to_bus not in pos:
            continue
        p1, p2 = pos[ln.from_bus], pos[ln.to_bus]
        scene.addItem(BranchItem(p1, p2, ln))
        fb, tb = bus_by_id.get(ln.from_bus), bus_by_id.get(ln.to_bus)
        if fb is not None and tb is not None and fb.base_kv != tb.base_kv:
            mid = QPointF((p1.x() + p2.x()) / 2.0, (p1.y() + p2.y()) / 2.0)
            scene.addItem(TransformerItem(mid, ln.id))

    # --- equipment grouped by bus --- #
    equip: dict[str, list] = defaultdict(list)
    for load in network.loads:
        equip[load.bus].append(("load", load))
    for gen in network.generators:
        equip[gen.bus].append(("gen", gen))
    for cap in network.capacitors:
        equip[cap.bus].append(("cap", cap))

    # --- buses + their equipment + source block --- #
    bus_items: dict[str, BusItem] = {}
    drop_pen = QPen(QColor(Colors.TEXT_MUTED), 2.0)
    for bus in network.buses:
        p = pos[bus.id]
        item = BusItem(bus)
        item.setPos(p)
        sol = sol_by_bus.get(bus.id)
        if sol is not None:
            item.set_solution(sol.v_pu, sol.angle_deg, sol.violation)
        scene.addItem(item)
        bus_items[bus.id] = item

        if bus.is_slack:
            scene.addItem(GridItem(QPointF(p.x() - 90.0, p.y()), 90.0 - BAR_WIDTH))

        attached = equip.get(bus.id, [])
        if attached:
            y = p.y() + BUS_HALF_H + 40.0
            for i, (kind, obj) in enumerate(attached):
                dx = 35.0 + i * 45.0
                center = QPointF(p.x() + dx, y)
                if kind == "load":
                    scene.addItem(LoadItem(center, obj))
                    y_top = y - 16.0
                elif kind == "gen":
                    scene.addItem(GeneratorItem(center, obj))
                    y_top = y - 28.0
                else:
                    scene.addItem(CapacitorItem(center, obj))
                    y_top = y - 16.0
                
                # Draw orthogonal connection line: right, then down
                y_bus = p.y() + 10.0 + i * 15.0
                scene.addLine(p.x(), y_bus, p.x() + dx, y_bus, drop_pen)
                scene.addLine(p.x() + dx, y_bus, p.x() + dx, y_top, drop_pen)

    scene.setSceneRect(scene.itemsBoundingRect().adjusted(-50, -50, 50, 50))
    return bus_items
