"""Common page scaffolding: breadcrumb + title + content frame.

Concrete views inherit from PageView and call ``set_content`` with their main widget.
This keeps every page consistent with the Gridscale X-style layout.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from gridlens.ui.shell.breadcrumb import Breadcrumb


class PageView(QWidget):
    page_key: str = ""
    page_title: str = ""
    breadcrumbs: list[str] = ["Projects"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._breadcrumb = Breadcrumb()
        self._breadcrumb.set_crumbs(self.breadcrumbs)

        self._title = QLabel(self.page_title)
        self._title.setObjectName("PageTitle")

        self._content = QFrame()
        self._content.setObjectName("ContentFrame")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(24, 0, 24, 16)

        self._layout.addWidget(self._breadcrumb)
        self._layout.addWidget(self._title)
        self._layout.addWidget(self._content, 1)

    def set_content(self, widget: QWidget) -> None:
        # Clear and replace. Pages typically only call this once.
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._content_layout.addWidget(widget)
