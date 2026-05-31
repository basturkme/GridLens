"""Headless tests for the in-app user manual (Help page)."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_manual_resource_exists() -> None:
    from gridlens._resources import resource

    path = resource("ui", "help", "user_manual.md")
    assert path.exists()
    assert "User Manual" in path.read_text(encoding="utf-8")


def test_help_view_renders_manual(qapp) -> None:
    from gridlens.ui.views.help_view import HelpView

    view = HelpView()
    text = view._browser.toMarkdown()
    assert "GridLens User Manual" in text
    assert "Editing operating conditions" in text


def test_help_button_navigates_to_manual(qapp) -> None:
    from gridlens.ui.main_window import MainWindow

    win = MainWindow()
    assert "help" in win._pages

    # Clicking the header "?" should switch the central stack to the Help page.
    win._header.helpRequested.emit()
    assert win._stack.currentWidget() is win._pages["help"]
