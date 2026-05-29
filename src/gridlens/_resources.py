"""Resolve packaged asset paths in dev and PyInstaller frozen builds.

In a frozen --onefile build PyInstaller extracts data files under
``sys._MEIPASS / "gridlens" / ...``. In dev they live next to the source
on disk. This helper papers over the difference so callers can write
``package_dir() / "ui" / "theme" / "style.qss"`` and not care.
"""
from __future__ import annotations

import sys
from pathlib import Path


def package_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "gridlens"
    return Path(__file__).resolve().parent


def resource(*parts: str) -> Path:
    return package_dir().joinpath(*parts)


def data_dir() -> Path:
    """Root of the bundled ``data/`` tree (example networks, format spec).

    In a frozen build PyInstaller is told to drop ``data/`` next to the
    extracted package (see gridlens.spec); in dev it lives at the repo root,
    two levels above this file (src/gridlens/_resources.py -> repo root).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "data"
    return Path(__file__).resolve().parents[2] / "data"


def default_example() -> Path | None:
    """Path to the example feeder shipped with the app, or None if absent."""
    candidate = data_dir() / "examples" / "4bus_radial.json"
    return candidate if candidate.exists() else None
