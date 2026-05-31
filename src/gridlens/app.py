"""Application entry point."""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from gridlens import __app_name__
from gridlens.ui.main_window import MainWindow
from gridlens.ui.theme import load_stylesheet


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(__app_name__)
    app.setStyleSheet(load_stylesheet())

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
