from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from gridlens.ui.views._base import PageView


class SolverView(PageView):
    page_key = "solver"
    page_title = "Solver"
    breadcrumbs = ["Projects", "Solver"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        body = QWidget()
        layout = QVBoxLayout(body)

        actions = QHBoxLayout()
        run_btn = QPushButton("Run Power Flow")
        run_btn.setObjectName("PrimaryButton")
        settings_btn = QPushButton("Solver Settings…")
        settings_btn.setObjectName("SecondaryButton")
        actions.addWidget(run_btn)
        actions.addWidget(settings_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        layout.addSpacing(8)
        layout.addWidget(QLabel("Convergence log"))
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText(
            "Solver output appears here once a network is loaded and 'Run' is pressed."
        )
        layout.addWidget(self._log, 1)

        self.set_content(body)
