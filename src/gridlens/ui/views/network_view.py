from __future__ import annotations

from functools import partial

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import (
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gridlens.core.models import Network, SolutionResult
from gridlens.ui.sld import build_scene
from gridlens.ui.sld.items import BranchItem, BusItem, TransformerItem, _EquipmentItem
from gridlens.ui.theme.colors import Colors
from gridlens.ui.views._base import PageView

_BUS_ROLE = Qt.ItemDataRole.UserRole
_KIND_ROLE = Qt.ItemDataRole.UserRole + 1
_ID_ROLE = Qt.ItemDataRole.UserRole + 2


class SLDView(QGraphicsView):
    """Interactive single-line-diagram canvas.

    QGraphicsScene is preferred over a matplotlib canvas for the SLD because
    Qt's item-based model gives first-class hit-testing, drag and selection.
    The scene is populated by :func:`gridlens.ui.sld.build_scene`; matplotlib is
    reserved for line charts in the reports view.
    """

    busPicked = pyqtSignal(str)
    itemPicked = pyqtSignal(str, str)  # (kind, id) for load / gen / cap symbols

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setBackgroundBrush(QColor(Colors.BG))
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
        self.select_item("bus", bus_id)

    def select_item(self, kind: str, obj_id: str) -> None:
        target_item = None
        for item in self._scene.items():
            if kind == "bus" and isinstance(item, BusItem) and item.bus_id == obj_id:
                target_item = item
                break
            elif kind == "line" and isinstance(item, BranchItem) and getattr(item, "line_id", None) == obj_id:
                target_item = item
                break
            elif isinstance(item, _EquipmentItem) and item.kind == kind and item.obj_id == obj_id:
                target_item = item
                break

        if target_item is None and kind == "line":
            for item in self._scene.items():
                if isinstance(item, TransformerItem) and getattr(item, "line_id", None) == obj_id:
                    target_item = item
                    break

        if target_item is None:
            return

        blocked = self._scene.blockSignals(True)
        self._scene.clearSelection()
        if kind == "line":
            for item in self._scene.items():
                if (isinstance(item, BranchItem) or isinstance(item, TransformerItem)) and getattr(item, "line_id", None) == obj_id:
                    item.setSelected(True)
        else:
            target_item.setSelected(True)
        self._scene.blockSignals(blocked)
        self.centerOn(target_item)

    def _on_selection_changed(self) -> None:
        for item in self._scene.selectedItems():
            if isinstance(item, BusItem):
                self.busPicked.emit(item.bus_id)
                return
            if isinstance(item, _EquipmentItem):
                self.itemPicked.emit(item.kind, item.obj_id)
                return
            if isinstance(item, BranchItem) and getattr(item, "line_id", None):
                self.itemPicked.emit("line", item.line_id)
                return
            if isinstance(item, TransformerItem) and getattr(item, "line_id", None):
                self.itemPicked.emit("line", item.line_id)
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
    itemPicked = pyqtSignal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._network: Network | None = None

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setSpacing(12)

        self._warning = QLabel()
        self._warning.setObjectName("WarningBanner")
        self._warning.setWordWrap(True)
        self._warning.hide()
        layout.addWidget(self._warning)

        self._search = QLineEdit()
        self._search.setObjectName("FilterInput")
        self._search.setPlaceholderText("Filter buses / equipment by name…")
        self._search.textChanged.connect(self._apply_filter)
        layout.addWidget(self._search)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Network", ""])
        self._tree.setMinimumWidth(280)
        self._tree.header().setStretchLastSection(False)
        self._tree.header().setSectionResizeMode(
            0, self._tree.header().ResizeMode.Stretch
        )
        self._tree.header().setSectionResizeMode(
            1, self._tree.header().ResizeMode.ResizeToContents
        )
        self._tree.itemClicked.connect(self._on_tree_clicked)
        splitter.addWidget(self._tree)

        self._sld = SLDView()
        self._sld.busPicked.connect(self._on_bus_picked)
        self._sld.itemPicked.connect(self.itemPicked)
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

        if solution is not None and not solution.converged:
            self._warning.setText(f"Power flow did not converge. {solution.message}")
            self._warning.show()
        else:
            self._warning.hide()

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

        def _add_equipment(
            parent: QTreeWidgetItem, label: str, kind: str, obj_id: str
        ) -> QTreeWidgetItem:
            """Add an equipment child with kind/id metadata and a Details button."""
            node = QTreeWidgetItem(parent, [label])
            node.setData(0, _KIND_ROLE, kind)
            node.setData(0, _ID_ROLE, obj_id)

            btn = QPushButton("\u25CE")  # ◎ bullseye (monochrome)
            btn.setObjectName("DetailsButton")
            btn.setToolTip("Details")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(28, 22)
            btn.clicked.connect(partial(self._on_details_clicked, kind, obj_id))
            self._tree.setItemWidget(node, 1, btn)
            return node

        # Category names mirror the Equipment page for consistency.
        buses = QTreeWidgetItem(self._tree, ["Buses"])
        for bus in network.buses:
            label = bus.name or bus.id
            sol = sol_by_bus.get(bus.id)
            if sol is not None:
                label += f"   {sol.v_pu:.3f} pu"
            node = QTreeWidgetItem(buses, [label])
            node.setData(0, _BUS_ROLE, bus.id)
            node.setData(0, _KIND_ROLE, "bus")
            node.setData(0, _ID_ROLE, bus.id)

            btn = QPushButton("\u25CE")  # ◎ bullseye (monochrome)
            btn.setObjectName("DetailsButton")
            btn.setToolTip("Details")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedSize(28, 22)
            btn.clicked.connect(partial(self._on_details_clicked, "bus", bus.id))
            self._tree.setItemWidget(node, 1, btn)

        lines = QTreeWidgetItem(self._tree, ["Lines"])
        for ln in network.lines:
            if ln.is_transformer:
                continue
            _add_equipment(lines, f"{ln.id}: {ln.from_bus} → {ln.to_bus}", "line", ln.id)

        transformers = [ln for ln in network.lines if ln.is_transformer]
        if transformers:
            xfmr_node = QTreeWidgetItem(self._tree, ["Transformers"])
            for ln in transformers:
                _add_equipment(
                    xfmr_node, f"{ln.id}: {ln.from_bus} → {ln.to_bus}", "line", ln.id
                )

        loads = QTreeWidgetItem(self._tree, ["Loads"])
        for load in network.loads:
            _add_equipment(loads, f"{load.id} @ {load.bus}", "load", load.id)

        gens = QTreeWidgetItem(self._tree, ["Generators"])
        for gen in network.generators:
            _add_equipment(gens, f"{gen.id} @ {gen.bus}", "gen", gen.id)

        capacitors_list = [c for c in network.capacitors if c.q_kvar >= 0]
        reactors_list = [c for c in network.capacitors if c.q_kvar < 0]

        if capacitors_list:
            caps = QTreeWidgetItem(self._tree, ["Capacitors"])
            for cap in capacitors_list:
                state = "on" if cap.in_service else "off"
                _add_equipment(caps, f"{cap.id} @ {cap.bus} ({state})", "cap", cap.id)

        if reactors_list:
            reactors = QTreeWidgetItem(self._tree, ["Reactors"])
            for cap in reactors_list:
                state = "on" if cap.in_service else "off"
                _add_equipment(reactors, f"{cap.id} @ {cap.bus} ({state})", "cap", cap.id)

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
        kind = item.data(0, _KIND_ROLE)
        obj_id = item.data(0, _ID_ROLE)
        if kind and obj_id:
            self._sld.select_item(kind, obj_id)
            if kind == "bus":
                self.busPicked.emit(obj_id)

    def _select_tree_item(self, kind: str, obj_id: str) -> None:
        for i in range(self._tree.topLevelItemCount()):
            top = self._tree.topLevelItem(i)
            for j in range(top.childCount()):
                child = top.child(j)
                if child.data(0, _KIND_ROLE) == kind and child.data(0, _ID_ROLE) == obj_id:
                    blocked = self._tree.blockSignals(True)
                    self._tree.setCurrentItem(child)
                    self._tree.blockSignals(blocked)
                    return

    def _on_details_clicked(self, kind: str, obj_id: str) -> None:
        """Navigate to the Equipment page for the given item."""
        self.itemPicked.emit(kind, obj_id)

    def _on_bus_picked(self, bus_id: str) -> None:
        self._select_tree_item("bus", bus_id)
        self.busPicked.emit(bus_id)
