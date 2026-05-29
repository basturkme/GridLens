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

from gridlens.core.models import Network, SolutionResult
from gridlens.ui.sld import build_scene
from gridlens.ui.sld.items import BusItem
from gridlens.ui.views._base import PageView

_BUS_ROLE = Qt.ItemDataRole.UserRole


class SLDView(QGraphicsView):
    """Interactive single-line-diagram canvas.

    QGraphicsScene is preferred over a matplotlib canvas for the SLD because
    Qt's item-based model gives first-class hit-testing, drag and selection.
    The scene is populated by :func:`gridlens.ui.sld.build_scene`; matplotlib is
    reserved for line charts in the reports view.
    """

    busPicked = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setBackgroundBrush(Qt.GlobalColor.white)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self._bus_items: dict[str, BusItem] = {}
        self._scene.selectionChanged.connect(self._on_selection_changed)
        self.render_network(None)

    def render_network(
        self, network: Network | None, solution: SolutionResult | None = None
    ) -> None:
        self._bus_items = build_scene(self._scene, network, solution)
        if network is not None and network.buses:
            self.fit()

    def fit(self) -> None:
        if not self._scene.itemsBoundingRect().isNull():
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def select_bus(self, bus_id: str) -> None:
        item = self._bus_items.get(bus_id)
        if item is None:
            return
        blocked = self._scene.blockSignals(True)
        self._scene.clearSelection()
        item.setSelected(True)
        self._scene.blockSignals(blocked)
        self.centerOn(item)

    def _on_selection_changed(self) -> None:
        for item in self._scene.selectedItems():
            if isinstance(item, BusItem):
                self.busPicked.emit(item.bus_id)
                return

    def wheelEvent(self, event) -> None:  # noqa: N802
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class NetworkView(PageView):
    """Two-pane content area: left category tree + right interactive SLD."""

    page_key = "network"
    page_title = "Network: (no file loaded)"
    breadcrumbs = ["Projects", "Network View"]

    busPicked = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._network: Network | None = None

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setSpacing(12)

        self._search = QLineEdit()
        self._search.setObjectName("FilterInput")
        self._search.setPlaceholderText("Filter buses / equipment by name…")
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabel("Network")
        self._tree.setMinimumWidth(240)
        self._tree.itemClicked.connect(self._on_tree_clicked)
        splitter.addWidget(self._tree)

        self._sld = SLDView()
        self._sld.busPicked.connect(self._on_bus_picked)
        splitter.addWidget(self._sld)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)
        self.set_content(body)

        self._populate_tree(None)

    # -- public API --------------------------------------------------------- #
    def set_network(
        self, network: Network | None, solution: SolutionResult | None = None
    ) -> None:
        self._network = network
        self._sld.render_network(network, solution)
        self._populate_tree(network, solution)
        if network is not None:
            self._title.setText(f"Network: {network.name or 'Untitled'}")
        else:
            self._title.setText(self.page_title)

    # -- tree --------------------------------------------------------------- #
    def _populate_tree(
        self, network: Network | None, solution: SolutionResult | None = None
    ) -> None:
        self._tree.clear()
        if network is None:
            QTreeWidgetItem(self._tree, ["No network loaded"])
            return

        sol_by_bus = (
            {b.bus_id: b for b in solution.bus_results}
            if solution is not None
            else {}
        )

        buses = QTreeWidgetItem(self._tree, ["Buses & Equipment"])
        for bus in network.buses:
            label = bus.name or bus.id
            sol = sol_by_bus.get(bus.id)
            if sol is not None:
                label += f"   {sol.v_pu:.3f} pu"
            node = QTreeWidgetItem(buses, [label])
            node.setData(0, _BUS_ROLE, bus.id)

        branches = QTreeWidgetItem(self._tree, ["Branches"])
        for ln in network.lines:
            QTreeWidgetItem(branches, [f"{ln.id}: {ln.from_bus} → {ln.to_bus}"])

        equipment = QTreeWidgetItem(self._tree, ["Loads / Generators / Capacitors"])
        for load in network.loads:
            QTreeWidgetItem(equipment, [f"Load {load.id} @ {load.bus}"])
        for gen in network.generators:
            QTreeWidgetItem(equipment, [f"Gen {gen.id} @ {gen.bus}"])
        for cap in network.capacitors:
            state = "on" if cap.in_service else "off"
            QTreeWidgetItem(equipment, [f"Cap {cap.id} @ {cap.bus} ({state})"])

        self._tree.expandAll()

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            any_visible = False
            for j in range(top.childCount()):
                child = top.child(j)
                bus_id = child.data(0, _BUS_ROLE) or ""
                haystack = f"{child.text(0)} {bus_id}".lower()
                match = needle in haystack
                child.setHidden(bool(needle) and not match)
                any_visible = any_visible or not child.isHidden()
            top.setHidden(bool(needle) and not any_visible)

    # -- selection sync ----------------------------------------------------- #
    def _on_tree_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        bus_id = item.data(0, _BUS_ROLE)
        if bus_id:
            self._sld.select_bus(bus_id)
            self.busPicked.emit(bus_id)

    def _on_bus_picked(self, bus_id: str) -> None:
        self.busPicked.emit(bus_id)
