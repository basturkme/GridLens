"""Headless tests for the file-management workflow (Sprint 5)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

from gridlens._resources import default_example  # noqa: E402
from gridlens.core.parser import ParserError  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def win(qapp):
    from gridlens.ui.main_window import MainWindow

    w = MainWindow()
    yield w


EXAMPLE = default_example()


def test_startup_example_loads(win) -> None:
    assert EXAMPLE is not None
    assert win.load_startup_example() is True
    assert win._network is not None
    assert len(win._network.buses) == 4
    # The bundled example must NOT become the save target, so a stray Ctrl+S
    # cannot overwrite the shipped reference; the user must Save As.
    assert win._current_path is None
    assert win._dirty is False


def test_bundled_example_is_not_overwritten_by_save(win, monkeypatch) -> None:
    # Load the example the way startup does, edit it, then trigger Save.
    win.load_startup_example()
    assert win._current_path is None
    win._network.loads[0].p_kw = 600.0
    win._on_network_edited()

    # With no current path, Save must fall back to Save As (a dialog), never
    # silently writing over the shipped example file.
    called = {}

    def fake_save_as():
        called["save_as"] = True
        return False

    monkeypatch.setattr(win, "_action_save_as", fake_save_as)
    win._action_save()
    assert called.get("save_as") is True


def test_open_path_sets_state_and_solves(win) -> None:
    win.open_path(EXAMPLE)
    assert win._solution is not None and win._solution.converged
    assert win._current_path == Path(EXAMPLE)
    assert win._dirty is False
    assert "[*]" in win.windowTitle()  # placeholder present (hidden until modified)


def test_save_round_trip_persists_edits(win, tmp_path: Path) -> None:
    win.open_path(EXAMPLE)
    win._network.loads[0].p_kw = 987.0
    out = tmp_path / "edited.json"
    win.save_to(out)
    assert out.exists()
    assert win._current_path == out
    assert win._dirty is False

    # Reload into a fresh window and confirm the edit survived.
    from gridlens.ui.main_window import MainWindow

    other = MainWindow()
    other.open_path(out)
    assert other._network.loads[0].p_kw == 987.0


def test_new_network_clears(win) -> None:
    win.open_path(EXAMPLE)
    win.new_network()
    assert win._network is None
    assert win._current_path is None
    assert win._dirty is False
    assert win.statusBar().currentMessage() == "Idle"


def test_edit_sets_dirty_then_save_clears(win, tmp_path: Path) -> None:
    win.open_path(EXAMPLE)
    assert win._dirty is False
    win._network.loads[0].p_kw = 500.0
    win._on_network_edited()  # simulates an accepted equipment edit
    assert win._dirty is True
    win.save_to(tmp_path / "n.json")
    assert win._dirty is False


def test_open_bad_file_raises_and_keeps_current(win, tmp_path: Path) -> None:
    win.open_path(EXAMPLE)
    original = win._network
    bad = tmp_path / "bad.json"
    bad.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ParserError):
        win.open_path(bad)
    assert win._network is original  # unchanged on failure


def test_open_non_radial_raises(win, tmp_path: Path) -> None:
    import json

    loopy = tmp_path / "loop.json"
    loopy.write_text(
        json.dumps(
            {
                "name": "loopy",
                "base_mva": 10.0,
                "buses": [
                    {"id": "A", "is_slack": True},
                    {"id": "B"},
                    {"id": "C"},
                ],
                "lines": [
                    {"id": "1", "from_bus": "A", "to_bus": "B"},
                    {"id": "2", "from_bus": "B", "to_bus": "C"},
                    {"id": "3", "from_bus": "C", "to_bus": "A"},
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ParserError, match="not radial"):
        win.open_path(loopy)


def test_title_shows_filename(win) -> None:
    win.open_path(EXAMPLE)
    assert EXAMPLE.name in win.windowTitle()
