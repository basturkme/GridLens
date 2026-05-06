from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel


class Footer(QFrame):
    """Bottom footer — totals on the left, secondary status on the right."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Footer")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._left = QLabel("Total: 0 buses, 0 lines")
        self._left.setObjectName("FooterText")
        self._right = QLabel("")
        self._right.setObjectName("FooterText")

        layout.addWidget(self._left)
        layout.addStretch(1)
        layout.addWidget(self._right)

    def set_totals(self, *, buses: int, lines: int, violations: int = 0) -> None:
        text = f"Total: {buses} buses, {lines} lines"
        if violations:
            text += f", {violations} violations"
        self._left.setText(text)

    def set_status(self, text: str) -> None:
        self._right.setText(text)
