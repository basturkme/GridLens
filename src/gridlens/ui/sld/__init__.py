"""Single-line-diagram rendering: custom QGraphicsItems + radial layout.

The SLD is drawn with Qt's item model (not matplotlib) so buses and equipment
get first-class hit-testing, selection and hover. ``build_scene`` populates a
QGraphicsScene from a :class:`~gridlens.core.models.Network`, optionally tinting
buses by their power-flow voltage violation.
"""
from __future__ import annotations

from gridlens.ui.sld.builder import build_scene
from gridlens.ui.sld.items import BusItem
from gridlens.ui.sld.layout import radial_layout

__all__ = ["build_scene", "radial_layout", "BusItem"]
