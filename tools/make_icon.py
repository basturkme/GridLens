"""Make the Windows .exe icon from a PNG.

Usage:
    python tools/make_icon.py path/to/logo.png

Writes ``src/gridlens/ui/assets/app.ico`` with the standard icon sizes. The build
spec (gridlens.spec) picks it up automatically on the next ``python build.py``.
A square image works best; non-square input is centre-padded to a square.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "gridlens" / "ui" / "assets" / "app.ico"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python tools/make_icon.py <image.png>")
        return 2
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"file not found: {src}")
        return 1

    img = Image.open(src).convert("RGBA")
    # Pad to a square so the icon is not distorted.
    side = max(img.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    square.save(OUT, format="ICO", sizes=SIZES)
    print(f"Wrote {OUT}")
    print("Now rebuild: python build.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
