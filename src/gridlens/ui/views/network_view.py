from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter
from PyQt6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QLineEdit,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gridlens.ui.views._base import PageView


class SLDView(QGraphicsView):
    """Interactive single-line-diagram canvas.

    QGraphicsScene is preferred over a matplotlib canvas for the SLD because
    Qt's item-based model gives first-class hit-testing, drag, and selection
    semantics. Sprint 3 will populate the scene with custom QGraphicsItem
    subclasses for buses, lines, transformers, loads, generators, capacitors.
    Matplotlib is reserved for line charts in the reports view.
    """

    busPicked = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setBackgroundBrush(Qt.GlobalColor.white)

        placeholder = self._scene.addText(
            "SLD canvas — load a network to render the single-line diagram."
        )
        placeholder.setDefaultTextColor(Qt.GlobalColor.gray)


class NetworkView(PageView):
    """Two-pane content area: left category tree + right interactive SLD."""

    page_key = "network"
    page_title = "Network: (no file loaded)"
    breadcrumbs = ["Projects", "Network View"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setSpacing(12)

        search = QLineEdit()
        search.setObjectName("FilterInput")
        search.setPlaceholderText("Filter buses / equipment by name…")
        layout.addWidget(search)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        tree = QTreeWidget()
        tree.setHeaderLabel("Bus")
        for category in (
            "Buses & Equipment",
            "Branches",
            "Loads / Generators / Capacitors",
            "Other",
        ):
            QTreeWidgetItem(tree, [category])
        tree.setMinimumWidth(220)
        splitter.addWidget(tree)

        self._sld = SLDView()
        splitter.addWidget(self._sld)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)
        self.set_content(body)
