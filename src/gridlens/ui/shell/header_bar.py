from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

from gridlens import __app_name__


class HeaderBar(QFrame):
    """Top bar — brand on the left, secondary icon buttons on the right."""

    helpRequested = pyqtSignal()
    openRequested = pyqtSignal()
    saveRequested = pyqtSignal()

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

        # Modern flat action icons (Open, Save, Help)
        actions = [
            ("\uD83D\uDCC1\uFE0E", "Open network file... (Ctrl+O)", self.openRequested),
            ("\uD83D\uDCBE\uFE0E", "Save network (Ctrl+S)", self.saveRequested),
            ("?", "Open the user manual", self.helpRequested),
        ]

        for label, tooltip, signal in actions:
            btn = QToolButton()
            btn.setObjectName("HeaderIcon")
            btn.setText(label)
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(signal.emit)
            layout.addWidget(btn)
