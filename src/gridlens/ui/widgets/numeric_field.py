from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLineEdit

from gridlens.utils.validators import parse_float


class NumericField(QLineEdit):
    """Single-line numeric input with live validation feedback.

    Emits valueChanged(float) when the input is valid.
    Visual invalid state is driven by the dynamic property [invalid="true"]
    so the QSS can style it red.
    """

    valueChanged = pyqtSignal(float)

    def __init__(
        self,
        *,
        minimum: float | None = None,
        maximum: float | None = None,
        allow_empty: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._min = minimum
        self._max = maximum
        self._allow_empty = allow_empty
        self.textChanged.connect(self._validate)

    def _validate(self, text: str) -> None:
        result = parse_float(
            text,
            minimum=self._min,
            maximum=self._max,
            allow_empty=self._allow_empty,
        )
        self.setProperty("invalid", "false" if result.ok else "true")
        self.setToolTip("" if result.ok else result.error)
        self.style().unpolish(self)
        self.style().polish(self)
        if result.ok and result.value is not None:
            self.valueChanged.emit(result.value)
