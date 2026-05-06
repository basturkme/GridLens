from __future__ import annotations

from gridlens._resources import resource

_QSS_PATH = resource("ui", "theme", "style.qss")


def load_stylesheet() -> str:
    return _QSS_PATH.read_text(encoding="utf-8")
