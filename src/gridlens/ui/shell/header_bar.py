from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

from gridlens import __app_name__


class HeaderBar(QFrame):
    """Top bar — brand on the left, secondary icon buttons on the right."""

    helpRequested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("HeaderBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(12)

        brand = QLabel(__app_name__)
        brand.setObjectName("HeaderBrand")

        title = QLabel("Distribution Feeder Analyzer")
        title.setObjectName("HeaderTitle")

        layout.addWidget(brand)
        layout.addWidget(title)
        layout.addStretch(1)

        for label in ("?", "\u2709\uFE0E", "A"):
            btn = QToolButton()
            btn.setObjectName("HeaderIcon")
            btn.setText(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if label == "?":
                btn.setToolTip("Open the user manual")
                btn.clicked.connect(self.helpRequested)
            layout.addWidget(btn)
