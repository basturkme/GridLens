# UI assets

Drop the home-page hero photo here as **`home_hero.jpg`**:

```
src/gridlens/ui/assets/home_hero.jpg
```

The home page loads it automatically (see `ui/views/home_view.py`). If the file
is missing, the banner falls back to a brand-coloured gradient, so the app still
runs. `.jpg` / `.png` assets in this folder are bundled into the frozen `.exe`
(see `gridlens.spec`).
