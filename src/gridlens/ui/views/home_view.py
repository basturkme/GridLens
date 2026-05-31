from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from gridlens.ui.views._base import PageView


class HomeView(PageView):
    page_key = "home"
    page_title = "Welcome to GridLens"
    breadcrumbs = ["Projects", "Home"]

    openRequested = pyqtSignal()
    reloadExampleRequested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        intro = QLabel(
            "Distribution feeder analyzer for radial three-phase balanced networks.\n"
            "Open a network file to begin, or run the solver on the example feeders."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        actions = QHBoxLayout()
        open_btn = QPushButton("Open Network File…")
        open_btn.setObjectName("PrimaryButton")
        open_btn.clicked.connect(self.openRequested)
        examples_btn = QPushButton("Load Example Feeder")
        examples_btn.setObjectName("SecondaryButton")
        examples_btn.clicked.connect(self.reloadExampleRequested)
        actions.addWidget(open_btn)
        actions.addWidget(examples_btn)
        actions.addStretch(1)
        layout.addSpacing(16)
        layout.addLayout(actions)
        layout.addStretch(1)

        self.set_content(body)
