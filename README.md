# GridLens

Distribution feeder analyzer for radial three-phase balanced networks.
EE 374 Fundamentals of Power Systems — 2025-2026 Spring term project.

GridLens turns a fixed feeder topology plus the current operating conditions
into immediate visibility of every bus voltage, and flags any bus that is out
of its allowed voltage band. It is built for field engineers: open a network,
adjust loads or switch a capacitor in or out, and read the result instantly.

## Features

- **VA (power-summation backward-forward sweep)** power-flow solver for radial
  networks (targets ≤10 buses), with adaptive under-relaxation for stiff cases.
- Reads the **standard course JSON format** (`system_data`, `bus_data`,
  `load_data`, `gen_data`, `shunt_data`, `line_data`, `transformer_data`): line
  impedances in ohms are converted to per-unit, transformers are separate
  branches, and shunt sign follows the spec (positive `q_mvar` = reactor).
- **Operating point entered by hand** — active/reactive power, and therefore
  power factor, are never assumed; the file carries only nameplate ratings.
- **Pinned leaf voltage:** hold a feeder-end voltage and the solver computes the
  grid (slack) voltage required to supply it.
- Single-line-diagram visualization with distinct symbols per equipment type.
- On-the-fly editing of loads, generators, capacitor/reactor banks and leaf-bus
  voltage, with the network re-solved and the diagram refreshed live.
- Automatic highlighting of voltage-magnitude violations (under / over).
- Solver page (adjustable tolerance / iteration limit, convergence log) and
  Reports page (results table, voltage-profile chart, CSV export).
- Open / Save / New workflow with input validation; a clear non-convergence
  warning appears on every page instead of a crash.
- Single-file portable Windows 11 executable.

## Status

All term-project features are implemented. The headless test suite (parser,
solver, diagram, equipment editing, file I/O, solver/reports views, robustness)
has **79 passing tests**. The executable builds via `build.py` and the user
manual is built into the app.

## Quick Start (Development)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m gridlens
```

Requires Python 3.11 or newer. On launch the bundled example feeder
(`data/examples/4bus_radial.json`) is loaded and solved automatically. Other
examples ship alongside it (`example_network`, `11bus_radial`, `15bus_*`).

## Build Executable

```powershell
python build.py
```

Produces `dist/GridLens.exe` — a portable Windows 11 executable that runs without
a separate Python installation, with every bundled example included.

## User Manual

A full user manual is built into the application: click the **?** button in the
top-right corner to open it on the Help page. The same content lives in
[`src/gridlens/ui/help/user_manual.md`](src/gridlens/ui/help/user_manual.md).

## Project Layout

```
src/gridlens/
  core/      VA solver, network model, course-format parser/validator
  ui/        PyQt6 frontend (shell, views, single-line-diagram, theme, assets)
  utils/     Validators, constants
data/        Example networks, file-format spec (FORMAT.md)
tests/       Headless pytest suite
docs/        Sprint plan and document outlines
```

## Tech Stack

Python 3.11 · PyQt6 · numpy · matplotlib · PyInstaller
