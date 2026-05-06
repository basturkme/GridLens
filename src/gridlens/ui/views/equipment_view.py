from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from gridlens.ui.views._base import PageView
from gridlens.ui.widgets.empty_state import EmptyState


class EquipmentView(PageView):
    page_key = "equipment"
    page_title = "Equipment"
    breadcrumbs = ["Projects", "Equipment"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        body = QWidget()
        layout = QVBoxLayout(body)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        tree = QTreeWidget()
        tree.setHeaderLabel("Category")
        for cat in ("Buses", "Lines", "Loads", "Generators", "Capacitors"):
            QTreeWidgetItem(tree, [cat])
        tree.setMinimumWidth(220)
        splitter.addWidget(tree)

        # Sprint 4 will swap this for the editor panel.
        splitter.addWidget(
            EmptyState(
                "No item selected",
                "Pick a category and an item to edit its parameters.",
            )
        )
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)
        self.set_content(body)
