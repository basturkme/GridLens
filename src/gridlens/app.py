"""Application entry point."""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from gridlens import __app_name__
from gridlens._resources import default_example
from gridlens.core import load_network, solve
from gridlens.core.models import Network, SolutionResult
from gridlens.ui.main_window import MainWindow
from gridlens.ui.theme import load_stylesheet


def _load_demo_network() -> tuple[Network, SolutionResult] | None:
    """Best-effort load + solve of the bundled example so the app opens with a
    populated single-line diagram. Returns None if the example is unavailable
    or fails to load (the app still starts with an empty canvas)."""
    path = default_example()
    if path is None:
        return None
    try:
        network = load_network(path)
        return network, solve(network)
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(__app_name__)
    app.setStyleSheet(load_stylesheet())

    window = MainWindow()
    demo = _load_demo_network()
    if demo is not None:
        window.set_network(*demo)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
