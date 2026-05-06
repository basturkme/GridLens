from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QVBoxLayout, QWidget

from gridlens.ui.views._base import PageView
from gridlens.ui.widgets.numeric_field import NumericField
from gridlens.utils import constants


class SettingsView(PageView):
    page_key = "settings"
    page_title = "Settings"
    breadcrumbs = ["Administration", "Settings"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        body = QWidget()
        outer = QVBoxLayout(body)
        form = QFormLayout()

        v_min = NumericField(minimum=0.5, maximum=1.5)
        v_min.setText(str(constants.V_MIN_PU))
        v_max = NumericField(minimum=0.5, maximum=1.5)
        v_max.setText(str(constants.V_MAX_PU))
        tol = NumericField(minimum=1e-9, maximum=1e-2)
        tol.setText(str(constants.DEFAULT_TOLERANCE_PU))
        max_iter = NumericField(minimum=1, maximum=1000)
        max_iter.setText(str(constants.DEFAULT_MAX_ITER))
        base_mva = NumericField(minimum=0.1, maximum=1000)
        base_mva.setText(str(constants.DEFAULT_BASE_MVA))

        form.addRow("Undervoltage threshold (pu)", v_min)
        form.addRow("Overvoltage threshold (pu)", v_max)
        form.addRow("Convergence tolerance (pu)", tol)
        form.addRow("Maximum iterations", max_iter)
        form.addRow("System base MVA", base_mva)

        outer.addLayout(form)
        outer.addStretch(1)
        self.set_content(body)
