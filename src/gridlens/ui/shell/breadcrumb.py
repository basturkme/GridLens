from __future__ import annotations

from PyQt6.QtWidgets import QLabel


class Breadcrumb(QLabel):
    """Lightweight breadcrumb. Pass crumbs as a list, e.g. ['Projects', 'Network View']."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Breadcrumb")
        self.set_crumbs(["Projects"])

    def set_crumbs(self, crumbs: list[str]) -> None:
        self.setText("  >  ".join(crumbs))
