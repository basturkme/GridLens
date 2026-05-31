from __future__ import annotations

from PyQt6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from gridlens._resources import resource
from gridlens.ui.views._base import PageView

_MANUAL = ("ui", "help", "user_manual.md")


class HelpView(PageView):
    """In-app user manual, rendered from the bundled Markdown file."""

    page_key = "help"
    page_title = "User Manual"
    breadcrumbs = ["Help", "User Manual"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        body = QWidget()
        layout = QVBoxLayout(body)

        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        self._browser.setMarkdown(self._manual_text())
        layout.addWidget(self._browser, 1)

        self.set_content(body)

    @staticmethod
    def _manual_text() -> str:
        try:
            return resource(*_MANUAL).read_text(encoding="utf-8")
        except OSError:
            return (
                "# User Manual\n\nThe manual file could not be loaded. "
                "See the project README for usage instructions."
            )
