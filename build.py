"""Build GridLens.exe via PyInstaller."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEC = ROOT / "gridlens.spec"


def main() -> int:
    for d in (ROOT / "build", ROOT / "dist"):
        if d.exists():
            shutil.rmtree(d)
    cmd = [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm"]
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
