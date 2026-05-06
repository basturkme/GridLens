from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QTableWidget, QVBoxLayout, QWidget

from gridlens.ui.views._base import PageView


class ReportsView(PageView):
    page_key = "reports"
    page_title = "Reports"
    breadcrumbs = ["Projects", "Reports"]

    HEADERS = ["Bus", "|V| (pu)", "∠V (°)", "|V| (kV)", "Status"]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        body = QWidget()
        layout = QVBoxLayout(body)

        toolbar = QHBoxLayout()
        export_btn = QPushButton("Export CSV")
        export_btn.setObjectName("SecondaryButton")
        toolbar.addStretch(1)
        toolbar.addWidget(export_btn)
        layout.addLayout(toolbar)

        table = QTableWidget(0, len(self.HEADERS))
        table.setHorizontalHeaderLabels(self.HEADERS)
        table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(table, 1)

        self.set_content(body)
