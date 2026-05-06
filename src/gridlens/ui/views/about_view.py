from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from gridlens import __app_name__, __version__
from gridlens.ui.views._base import PageView


class AboutView(PageView):
    page_key = "about"
    page_title = "About"
    breadcrumbs = ["Administration", "About"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        body = QWidget()
        layout = QVBoxLayout(body)

        text = QLabel(
            f"<b>{__app_name__}</b> v{__version__}<br><br>"
            "Distribution feeder analyzer for radial three-phase balanced networks.<br>"
            "EE 374 Fundamentals of Power Systems — 2025-2026 Spring term project."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        layout.addStretch(1)

        self.set_content(body)
