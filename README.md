# GridLens

Distribution feeder analyzer for radial three-phase balanced networks.
EE 374 Fundamentals of Power Systems — 2025-2026 Spring term project.

## Features

- VA (Backward-Forward Sweep) power flow solver for radial networks (≤10 buses)
- Single-line-diagram visualization with equipment differentiation
- On-the-fly editing of loads, generators, capacitor banks, and leaf-bus voltage
- Automatic highlighting of voltage-magnitude violations
- Single-file portable Windows executable

## Quick Start (Development)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m gridlens
```

## Build Executable

```powershell
python build.py
```

Produces `dist/GridLens.exe` — copy and run on any Windows 11 machine.

## Project Layout

```
src/gridlens/
  core/      VA solver, network models, file parser
  ui/        PyQt6 frontend (Gridscale X-style shell)
  utils/     Validators, constants
data/        Example networks, file format spec
tests/       pytest cases (IEEE reference networks)
docs/        User manual & infographic outlines
```

## Tech Stack

Python 3.11 · PyQt6 · numpy · matplotlib · PyInstaller
