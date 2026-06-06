"""Generate the default GridLens app icon (a blue tile with a white bolt).

Writes ``src/gridlens/ui/assets/app.ico`` (and a matching .png). The build spec
picks the .ico up automatically on the next ``python build.py``. Replace it with
your own via ``python tools/make_icon.py logo.png`` if you prefer a custom logo.

    python tools/make_logo.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "gridlens" / "ui" / "assets"
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

S = 256
BRAND = (59, 130, 246, 255)      # #3B82F6
BRAND_DARK = (37, 99, 235, 255)  # #2563EB
WHITE = (255, 255, 255, 255)


def render() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Rounded tile with a subtle border.
    d.rounded_rectangle([8, 8, S - 8, S - 8], radius=52, fill=BRAND, outline=BRAND_DARK, width=6)

    # Lightning bolt (power) centred on the tile.
    bolt = [
        (150, 40), (96, 140), (132, 140), (106, 216),
        (172, 112), (134, 112), (160, 40),
    ]
    d.polygon(bolt, fill=WHITE)
    return img


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    img = render()
    (ASSETS / "app.png").write_bytes(b"")  # placeholder so path exists if save fails
    img.save(ASSETS / "app.png", format="PNG")
    img.save(ASSETS / "app.ico", format="ICO", sizes=SIZES)
    print(f"Wrote {ASSETS / 'app.ico'} and app.png")
    print("Now rebuild: python build.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
