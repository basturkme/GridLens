from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSizePolicy, QToolButton


class NavButton(QToolButton):
    """Sidebar navigation button (Gridscale X-style)."""

    def __init__(self, label: str, icon_text: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("NavButton")
        self.setText(f"  {icon_text}  {label}" if icon_text else f"  {label}")
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
