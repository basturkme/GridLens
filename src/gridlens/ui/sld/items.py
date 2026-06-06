"""Custom QGraphicsItems for the single-line diagram.

Each electrical element is its own item so the canvas can hit-test, select and
hover them individually. Symbols deliberately echo the project's Figure 1: buses
are vertical bars, the source is a "Power Grid" block, a winding-change between
two buses draws a transformer, loads are down-arrows, generators a circled sine,
capacitors a two-plate symbol.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from gridlens.core.models import Bus, Capacitor, Generator, Line, Load
from gridlens.ui.theme.colors import Colors

BUS_HALF_H = 36.0
BAR_WIDTH = 5.0

_VIOLATION_COLOR = {
    "ok": Colors.OK,
    "under": Colors.UNDER,
    "over": Colors.OVER,
}


def _font(size: int, bold: bool = False) -> QFont:
    f = QFont("Segoe UI", size)
    f.setBold(bold)
    return f


# --------------------------------------------------------------------------- #
# Bus bar (selectable / hoverable — the primary pick target)
# --------------------------------------------------------------------------- #
class BusItem(QGraphicsItem):
    def __init__(self, bus: Bus, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)
        self.bus = bus
        self.bus_id = bus.id
        self._violation = "none"
        self._v_text = ""
        self._hover = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)
        self.setToolTip(self._tooltip())

    # -- state -------------------------------------------------------------- #
    def set_solution(self, v_pu: float, angle_deg: float, violation: str) -> None:
        self._violation = violation
        self._v_text = f"{v_pu:.3f} pu  ∠{angle_deg:+.1f}°"
        self.setToolTip(self._tooltip())
        self.update()

    def _tooltip(self) -> str:
        label = self.bus.name or self.bus.id
        parts = [f"{label}", f"Base: {self.bus.base_kv:g} kV"]
        if self.bus.is_slack:
            parts.append("Slack / source")
        if self.bus.is_leaf:
            parts.append("Leaf")
        if self._v_text:
            parts.append(self._v_text)
        return "\n".join(parts)

    def _color(self) -> QColor:
        return QColor(_VIOLATION_COLOR.get(self._violation, Colors.BRAND))

    # -- geometry ----------------------------------------------------------- #
    def boundingRect(self) -> QRectF:
        return QRectF(-72.0, -BUS_HALF_H - 26.0, 144.0, 2 * BUS_HALF_H + 52.0)

    def hoverEnterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        color = self._color()
        selected = self.isSelected()

        # Highlight halo on hover / selection.
        if self._hover or selected:
            halo = QColor(Colors.BRAND)
            halo.setAlpha(60 if not selected else 110)
            painter.setPen(QPen(halo, BAR_WIDTH + 10, Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(0, -BUS_HALF_H), QPointF(0, BUS_HALF_H))

        painter.setPen(QPen(color, BAR_WIDTH, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(0, -BUS_HALF_H), QPointF(0, BUS_HALF_H))

        # Name above the bar.
        painter.setPen(QColor(Colors.TEXT))
        painter.setFont(_font(9, bold=True))
        painter.drawText(
            QRectF(-72.0, -BUS_HALF_H - 24.0, 144.0, 18.0),
            int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
            self.bus.name or self.bus.id,
        )

        # Voltage / violation below the bar.
        if self._v_text:
            painter.setPen(color)
            painter.setFont(_font(8))
            painter.drawText(
                QRectF(-72.0, BUS_HALF_H + 4.0, 144.0, 18.0),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
                self._v_text,
            )


# --------------------------------------------------------------------------- #
# Branch (line) — orthogonal connector behind the buses
# --------------------------------------------------------------------------- #
class BranchItem(QGraphicsItem):
    def __init__(self, p1: QPointF, p2: QPointF, line: Line) -> None:
        super().__init__()
        self._p1 = p1
        self._p2 = p2
        self.line_id = line.id
        self.setZValue(1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self._hover = False
        if getattr(line, "is_transformer", False):
            self.setToolTip(
                f"Transformer {line.id}\n{line.from_bus} → {line.to_bus}\n"
                f"X = {line.x_pu:g} pu (system base)"
            )
        else:
            self.setToolTip(
                f"Line {line.id}\n{line.from_bus} → {line.to_bus}\n"
                f"Z = {line.r_pu:g} + j{line.x_pu:g} pu"
            )

    def _path(self) -> QPainterPath:
        mid_x = (self._p1.x() + self._p2.x()) / 2.0
        path = QPainterPath(self._p1)
        path.lineTo(QPointF(mid_x, self._p1.y()))
        path.lineTo(QPointF(mid_x, self._p2.y()))
        path.lineTo(self._p2)
        return path

    def boundingRect(self) -> QRectF:
        return self._path().boundingRect().adjusted(-6, -6, 6, 6)

    def hoverEnterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()

    def paint(self, painter, option, widget=None) -> None:
        selected = self.isSelected()
        if self._hover or selected:
            halo = QColor(Colors.BRAND)
            halo.setAlpha(60 if not selected else 110)
            painter.setPen(QPen(halo, 8.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawPath(self._path())

        color = Colors.BRAND if selected else Colors.TEXT_MUTED
        painter.setPen(QPen(QColor(color), 2.0))
        painter.drawPath(self._path())


# --------------------------------------------------------------------------- #
# Equipment symbols
# --------------------------------------------------------------------------- #
class TransformerItem(QGraphicsItem):
    """Two interlocking windings, drawn where two buses differ in base kV."""

    def __init__(self, center: QPointF, line_id: str | None = None) -> None:
        super().__init__()
        self.setPos(center)
        self.line_id = line_id
        self.setZValue(5)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self._hover = False
        self.setToolTip(f"Transformer {line_id}\n(winding change)" if line_id else "Transformer (winding change)")

    def boundingRect(self) -> QRectF:
        return QRectF(-22.0, -14.0, 44.0, 28.0)

    def hoverEnterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()

    def paint(self, painter, option, widget=None) -> None:
        selected = self.isSelected()
        if self._hover or selected:
            halo = QColor(Colors.BRAND)
            halo.setAlpha(60 if not selected else 110)
            painter.setPen(QPen(halo, 8.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(-7.0, 0.0), 12.0, 12.0)
            painter.drawEllipse(QPointF(7.0, 0.0), 12.0, 12.0)

        painter.setPen(QPen(QColor(Colors.BRAND if not selected else Colors.BRAND), 3.0 if selected else 2.0))
        painter.setBrush(QBrush(QColor(Colors.BG)))
        painter.drawEllipse(QPointF(-7.0, 0.0), 10.0, 10.0)
        painter.drawEllipse(QPointF(7.0, 0.0), 10.0, 10.0)


class _EquipmentItem(QGraphicsItem):
    """Base for clickable equipment symbols: carries its (kind, id) and is
    selectable so the canvas can route a click to the matching editor."""

    kind = ""

    def __init__(self, center: QPointF, obj_id: str) -> None:
        super().__init__()
        self.obj_id = obj_id
        self.setPos(center)
        self.setZValue(8)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAcceptHoverEvents(True)
        self._hover = False

    def hoverEnterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()

    def draw_highlight(self, painter: QPainter) -> None:
        selected = self.isSelected()
        if self._hover or selected:
            halo = QColor(Colors.BRAND)
            halo.setAlpha(60 if not selected else 110)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(halo))
            painter.drawRoundedRect(self.boundingRect().adjusted(-4, -4, 4, 4), 6, 6)


class LoadItem(_EquipmentItem):
    kind = "load"

    def __init__(self, center: QPointF, load: Load) -> None:
        super().__init__(center, load.id)
        self.setToolTip(f"Load {load.id}\n{load.p_kw:g} kW, {load.q_kvar:g} kvar")

    def boundingRect(self) -> QRectF:
        return QRectF(-10.0, -16.0, 20.0, 34.0)

    def paint(self, painter, option, widget=None) -> None:
        self.draw_highlight(painter)
        pen = QPen(QColor(Colors.TEXT), 2.0)
        painter.setPen(pen)
        painter.drawLine(QPointF(0.0, -16.0), QPointF(0.0, 2.0))
        painter.setBrush(QBrush(QColor(Colors.TEXT)))
        arrow = QPainterPath(QPointF(-8.0, 2.0))
        arrow.lineTo(QPointF(8.0, 2.0))
        arrow.lineTo(QPointF(0.0, 16.0))
        arrow.closeSubpath()
        painter.drawPath(arrow)


class GeneratorItem(_EquipmentItem):
    kind = "gen"

    def __init__(self, center: QPointF, gen: Generator) -> None:
        super().__init__(center, gen.id)
        self.setToolTip(f"Generator {gen.id}\n{gen.p_kw:g} kW, {gen.q_kvar:g} kvar")

    def boundingRect(self) -> QRectF:
        return QRectF(-14.0, -28.0, 28.0, 44.0)

    def paint(self, painter, option, widget=None) -> None:
        self.draw_highlight(painter)
        painter.setPen(QPen(QColor(Colors.OK), 2.0))
        painter.drawLine(QPointF(0.0, -28.0), QPointF(0.0, -13.0))
        painter.setBrush(QBrush(QColor(Colors.BG)))
        painter.drawEllipse(QPointF(0.0, 0.0), 13.0, 13.0)
        # Sine wave inside the circle.
        wave = QPainterPath(QPointF(-8.0, 0.0))
        wave.cubicTo(QPointF(-4.0, -9.0), QPointF(-1.0, -9.0), QPointF(0.0, 0.0))
        wave.cubicTo(QPointF(1.0, 9.0), QPointF(4.0, 9.0), QPointF(8.0, 0.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(wave)


class CapacitorItem(_EquipmentItem):
    kind = "cap"

    def __init__(self, center: QPointF, cap: Capacitor) -> None:
        super().__init__(center, cap.id)
        self._in_service = cap.in_service
        self._q_kvar = cap.q_kvar
        state = "in service" if cap.in_service else "out of service"
        name = "Reactor" if cap.q_kvar < 0 else "Capacitor"
        val = abs(cap.q_kvar)
        unit = "kvar (consuming)" if cap.q_kvar < 0 else "kvar"
        self.setToolTip(f"{name} {cap.id}\n{val:g} {unit} ({state})")

    def boundingRect(self) -> QRectF:
        return QRectF(-12.0, -16.0, 24.0, 34.0)

    def paint(self, painter, option, widget=None) -> None:
        self.draw_highlight(painter)
        color = QColor(Colors.BRAND if self._in_service else Colors.BORDER)
        painter.setPen(QPen(color, 2.0))

        if self._q_kvar < 0:
            # Draw Inductor coil symbol (Reactor)
            painter.drawLine(QPointF(0.0, -16.0), QPointF(0.0, -10.0))
            
            coil = QPainterPath(QPointF(0.0, -10.0))
            coil.cubicTo(QPointF(6.0, -10.0), QPointF(6.0, -4.0), QPointF(0.0, -4.0))
            coil.cubicTo(QPointF(6.0, -4.0), QPointF(6.0, 2.0), QPointF(0.0, 2.0))
            coil.cubicTo(QPointF(6.0, 2.0), QPointF(6.0, 8.0), QPointF(0.0, 8.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(coil)
            
            painter.drawLine(QPointF(0.0, 8.0), QPointF(0.0, 10.0))
            painter.drawLine(QPointF(-7.0, 14.0), QPointF(7.0, 14.0))
        else:
            # Draw Capacitor symbol
            painter.drawLine(QPointF(0.0, -16.0), QPointF(0.0, -3.0))
            painter.drawLine(QPointF(-11.0, -3.0), QPointF(11.0, -3.0))
            painter.drawLine(QPointF(-11.0, 3.0), QPointF(11.0, 3.0))
            painter.drawLine(QPointF(0.0, 3.0), QPointF(0.0, 10.0))
            painter.drawLine(QPointF(-7.0, 14.0), QPointF(7.0, 14.0))


class GridItem(QGraphicsItem):
    """The upstream source ("Power Grid" block) to the left of the slack bus."""

    def __init__(self, anchor: QPointF, reach: float) -> None:
        super().__init__()
        self.setPos(anchor)
        self._reach = reach  # horizontal distance to the slack bus centre
        self.setZValue(3)
        self.setToolTip("Power Grid (slack source)")

    def boundingRect(self) -> QRectF:
        return QRectF(-78.0, -24.0, self._reach + 80.0, 48.0)

    def paint(self, painter, option, widget=None) -> None:
        painter.setPen(QPen(QColor(Colors.TEXT_MUTED), 2.0))
        painter.setBrush(QBrush(QColor(Colors.BG_PANEL)))
        painter.drawRoundedRect(QRectF(-76.0, -20.0, 72.0, 40.0), 4.0, 4.0)
        painter.setPen(QColor(Colors.TEXT))
        painter.setFont(_font(8, bold=True))
        painter.drawText(
            QRectF(-76.0, -20.0, 72.0, 40.0),
            int(Qt.AlignmentFlag.AlignCenter),
            "Power\nGrid",
        )
        # Feeder stub to the slack bus.
        painter.setPen(QPen(QColor(Colors.TEXT_MUTED), 2.0))
        painter.drawLine(QPointF(-4.0, 0.0), QPointF(self._reach, 0.0))
