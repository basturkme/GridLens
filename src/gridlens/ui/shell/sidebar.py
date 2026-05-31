from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gridlens.ui.widgets.nav_button import NavButton

NAV_ITEMS: list[tuple[str, str, str]] = [
    # (page_key, group, label)
    ("home", "", "\u2302  Home"),
    ("network", "Project", "\u25A6  Network"),
    ("solver", "Project", "\u26A1\uFE0E  Solver"),
    ("equipment", "Project", "\u2699\uFE0E  Equipment"),
    ("reports", "Project", "\u25A4  Reports"),
    ("settings", "Administration", "\u2630  Settings"),
    ("about", "Administration", "\u2139\uFE0E  About"),
]


class Sidebar(QFrame):
    """Collapsible left navigation, mirrors Gridscale X structure."""

    pageChanged = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setProperty("collapsed", "false")
        self._collapsed = False
        self._buttons: dict[str, NavButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 8)
        outer.setSpacing(0)

        collapse_row = QHBoxLayout()
        collapse_row.setContentsMargins(8, 0, 8, 8)
        self._collapse_btn = QToolButton()
        self._collapse_btn.setObjectName("SidebarCollapse")
        self._collapse_btn.setText("«")
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.clicked.connect(self.toggle_collapsed)
        collapse_row.addStretch(1)
        collapse_row.addWidget(self._collapse_btn)
        outer.addLayout(collapse_row)

        current_group = ""
        for key, group, label in NAV_ITEMS:
            if group != current_group:
                if group:
                    section = QLabel(group)
                    section.setObjectName("SidebarSection")
                    outer.addWidget(section)
                current_group = group
            btn = NavButton(label)
            btn.clicked.connect(lambda _checked=False, k=key: self._on_clicked(k))
            outer.addWidget(btn)
            self._buttons[key] = btn

        outer.addStretch(1)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

    def select(self, page_key: str) -> None:
        btn = self._buttons.get(page_key)
        if btn is not None:
            btn.setChecked(True)

    def _on_clicked(self, page_key: str) -> None:
        self.pageChanged.emit(page_key)

    def toggle_collapsed(self) -> None:
        self._collapsed = not self._collapsed
        self.setProperty("collapsed", "true" if self._collapsed else "false")
        self._collapse_btn.setText("»" if self._collapsed else "«")
        self.style().unpolish(self)
        self.style().polish(self)
