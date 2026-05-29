"""Equipment editor — modify operating conditions on the fly.

Per the project brief a field engineer must be able to edit, without reloading
the network: load P/Q, generator P/Q, a capacitor bank's in-service state, and
the pinned voltage of a leaf bus. Selecting an item on the left builds a small
validated form on the right; every accepted change mutates the Network model in
place and emits :pyattr:`EquipmentView.networkEdited` so the shell can re-solve
and refresh the diagram immediately.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gridlens.core.models import Network, SolutionResult
from gridlens.ui.views._base import PageView
from gridlens.ui.widgets.empty_state import EmptyState
from gridlens.ui.widgets.numeric_field import NumericField

_KIND_ROLE = Qt.ItemDataRole.UserRole
_ID_ROLE = Qt.ItemDataRole.UserRole + 1


class EquipmentView(PageView):
    page_key = "equipment"
    page_title = "Equipment"
    breadcrumbs = ["Projects", "Equipment"]

    networkEdited = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self._network: Network | None = None
        self._solution: SolutionResult | None = None
        # Read-only "solved |V|" label for the bus currently in the editor, so
        # it can be refreshed after a re-solve without rebuilding the form.
        self._voltage_label: QLabel | None = None
        self._voltage_bus_id: str | None = None

        body = QWidget()
        layout = QVBoxLayout(body)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabel("Category")
        self._tree.setMinimumWidth(240)
        self._tree.itemClicked.connect(self._on_item_clicked)
        splitter.addWidget(self._tree)

        self._editor_holder = QWidget()
        self._editor_layout = QVBoxLayout(self._editor_holder)
        self._editor_layout.setContentsMargins(16, 8, 16, 8)
        splitter.addWidget(self._editor_holder)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)
        self.set_content(body)

        self._populate_tree()
        self._show_placeholder()

    # -- public API --------------------------------------------------------- #
    def set_network(
        self, network: Network | None, solution: SolutionResult | None = None
    ) -> None:
        self._network = network
        self._solution = solution
        self._voltage_label = None
        self._voltage_bus_id = None
        self._populate_tree()
        self._show_placeholder()

    def apply_solution(self, solution: SolutionResult | None) -> None:
        """Refresh the live voltage readout after a re-solve, leaving the rest
        of the open editor (and the user's focus) untouched."""
        self._solution = solution
        if self._voltage_label is not None and self._voltage_bus_id is not None:
            self._voltage_label.setText(self._voltage_text(self._voltage_bus_id))

    # -- tree --------------------------------------------------------------- #
    def _populate_tree(self) -> None:
        self._tree.clear()
        net = self._network
        if net is None:
            QTreeWidgetItem(self._tree, ["No network loaded"])
            return

        def add(parent: QTreeWidgetItem, label: str, kind: str, obj_id: str) -> None:
            node = QTreeWidgetItem(parent, [label])
            node.setData(0, _KIND_ROLE, kind)
            node.setData(0, _ID_ROLE, obj_id)

        buses = QTreeWidgetItem(self._tree, ["Buses"])
        for b in net.buses:
            tag = " (leaf)" if b.is_leaf else (" (slack)" if b.is_slack else "")
            add(buses, f"{b.name or b.id}{tag}", "bus", b.id)

        lines = QTreeWidgetItem(self._tree, ["Lines"])
        for ln in net.lines:
            add(lines, f"{ln.id}: {ln.from_bus} → {ln.to_bus}", "line", ln.id)

        loads = QTreeWidgetItem(self._tree, ["Loads"])
        for x in net.loads:
            add(loads, f"{x.id} @ {x.bus}", "load", x.id)

        gens = QTreeWidgetItem(self._tree, ["Generators"])
        for x in net.generators:
            add(gens, f"{x.id} @ {x.bus}", "gen", x.id)

        caps = QTreeWidgetItem(self._tree, ["Capacitors"])
        for x in net.capacitors:
            add(caps, f"{x.id} @ {x.bus}", "cap", x.id)

        self._tree.expandAll()

    # -- selection --------------------------------------------------------- #
    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        kind = item.data(0, _KIND_ROLE)
        obj_id = item.data(0, _ID_ROLE)
        if not kind or self._network is None:
            return
        self._voltage_label = None
        self._voltage_bus_id = None
        editor = self._editor_for(kind, obj_id)
        if editor is not None:
            self._set_editor(editor)

    def _editor_for(self, kind: str, obj_id: str) -> QWidget | None:
        net = self._network
        assert net is not None
        if kind == "load":
            obj = _find(net.loads, obj_id)
            return self._power_editor(obj, "Load") if obj else None
        if kind == "gen":
            obj = _find(net.generators, obj_id)
            return self._power_editor(obj, "Generator") if obj else None
        if kind == "cap":
            obj = _find(net.capacitors, obj_id)
            return self._capacitor_editor(obj) if obj else None
        if kind == "bus":
            obj = _find(net.buses, obj_id)
            return self._bus_editor(obj) if obj else None
        if kind == "line":
            obj = _find(net.lines, obj_id)
            return self._line_editor(obj) if obj else None
        return None

    # -- editors ----------------------------------------------------------- #
    def _power_editor(self, obj, title: str) -> QWidget:
        w, form = _form(f"{title} {obj.id}", f"Connected at bus {obj.bus}")

        p_field = NumericField()
        p_field.setText(f"{obj.p_kw:g}")
        p_field.valueChanged.connect(lambda v: self._set_attr(obj, "p_kw", v))
        form.addRow("Active power P (kW)", p_field)

        q_field = NumericField()
        q_field.setText(f"{obj.q_kvar:g}")
        q_field.valueChanged.connect(lambda v: self._set_attr(obj, "q_kvar", v))
        form.addRow("Reactive power Q (kvar)", q_field)
        return w

    def _capacitor_editor(self, cap) -> QWidget:
        w, form = _form(f"Capacitor {cap.id}", f"Connected at bus {cap.bus}")

        q_field = NumericField(minimum=0.0)
        q_field.setText(f"{cap.q_kvar:g}")
        q_field.valueChanged.connect(lambda v: self._set_attr(cap, "q_kvar", v))
        form.addRow("Rating Q (kvar)", q_field)

        in_service = QCheckBox("In service")
        in_service.setChecked(cap.in_service)
        in_service.toggled.connect(lambda on: self._set_attr(cap, "in_service", on))
        form.addRow("State", in_service)
        return w

    def _bus_editor(self, bus) -> QWidget:
        subtitle = (
            "Leaf bus — operator may pin its voltage."
            if bus.is_leaf
            else "Voltage is computed by the solver."
        )
        w, form = _form(f"Bus {bus.name or bus.id}", subtitle)
        form.addRow("Base voltage (kV)", QLabel(f"{bus.base_kv:g}"))

        self._voltage_label = QLabel(self._voltage_text(bus.id))
        self._voltage_bus_id = bus.id
        form.addRow("Solved |V|", self._voltage_label)

        if bus.is_leaf:
            hold = QCheckBox("Hold this voltage (pu)")
            hold.setChecked(bus.v_set_pu is not None)
            v_field = NumericField(minimum=0.8, maximum=1.2)
            v_field.setText(f"{bus.v_set_pu:g}" if bus.v_set_pu is not None else "1.00")
            v_field.setEnabled(bus.v_set_pu is not None)

            def on_toggle(_checked: bool) -> None:
                on = hold.isChecked()
                v_field.setEnabled(on)
                if not on:
                    bus.v_set_pu = None
                    self.networkEdited.emit()
                else:
                    result = _parse(v_field, 0.8, 1.2)
                    bus.v_set_pu = result if result is not None else 1.0
                    self.networkEdited.emit()

            def on_value(v: float) -> None:
                if hold.isChecked():
                    bus.v_set_pu = v
                    self.networkEdited.emit()

            hold.toggled.connect(on_toggle)
            v_field.valueChanged.connect(on_value)
            form.addRow(hold, v_field)
        return w

    def _line_editor(self, line) -> QWidget:
        w, form = _form(f"Line {line.id}", f"{line.from_bus} → {line.to_bus}")
        form.addRow("R (pu)", QLabel(f"{line.r_pu:g}"))
        form.addRow("X (pu)", QLabel(f"{line.x_pu:g}"))
        form.addRow("Shunt B (pu)", QLabel(f"{line.b_pu:g}"))
        form.addRow(QLabel("Line parameters are fixed network data."))
        return w

    # -- helpers ----------------------------------------------------------- #
    def _set_attr(self, obj, attr: str, value) -> None:
        setattr(obj, attr, value)
        self.networkEdited.emit()

    def _voltage_text(self, bus_id: str) -> str:
        if self._solution is None:
            return "—"
        for b in self._solution.bus_results:
            if b.bus_id == bus_id:
                flag = "" if b.violation == "ok" else f"  ⚠ {b.violation}voltage"
                return f"{b.v_pu:.4f} pu  ∠{b.angle_deg:+.2f}°{flag}"
        return "—"

    def _set_editor(self, widget: QWidget) -> None:
        while self._editor_layout.count():
            item = self._editor_layout.takeAt(0)
            old = item.widget()
            if old is not None:
                old.deleteLater()
        self._editor_layout.addWidget(widget)

    def _show_placeholder(self) -> None:
        if self._network is None:
            self._set_editor(
                EmptyState("No network loaded", "Open a network to edit equipment.")
            )
        else:
            self._set_editor(
                EmptyState(
                    "No item selected",
                    "Pick a bus or equipment item on the left to edit its values.",
                )
            )


def _form(title: str, subtitle: str = "") -> tuple[QWidget, QFormLayout]:
    w = QWidget()
    outer = QVBoxLayout(w)
    outer.setContentsMargins(0, 0, 0, 0)

    heading = QLabel(title)
    heading.setObjectName("EmptyTitle")
    outer.addWidget(heading)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setObjectName("EmptySubtitle")
        outer.addWidget(sub)

    form_host = QWidget()
    form = QFormLayout(form_host)
    form.setContentsMargins(0, 12, 0, 0)
    form.setHorizontalSpacing(16)
    form.setVerticalSpacing(10)
    outer.addWidget(form_host)
    outer.addStretch(1)
    return w, form


def _find(items, obj_id):
    return next((x for x in items if x.id == obj_id), None)


def _parse(field: NumericField, lo: float, hi: float) -> float | None:
    from gridlens.utils.validators import parse_float

    result = parse_float(field.text(), minimum=lo, maximum=hi)
    return result.value if result.ok else None
