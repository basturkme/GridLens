# GridLens

Distribution feeder analyzer for radial three-phase balanced networks.
EE 374 Fundamentals of Power Systems — 2025-2026 Spring term project.

GridLens turns a fixed feeder topology plus the current operating conditions
into immediate visibility of every bus voltage, and flags any bus that is out
of its allowed voltage band. It is built for field engineers: open a network,
adjust loads or switch a capacitor in or out, and read the result instantly.

## Features

- VA (Backward-Forward Sweep) power-flow solver for radial networks (up to 10 buses)
- Operator-pinned leaf-bus voltage held via an outer reactive-compensation loop
- Single-line-diagram visualization with distinct symbols per equipment type
- On-the-fly editing of loads, generators, capacitor banks, and leaf-bus voltage,
  with the network re-solved and the diagram refreshed live
- Automatic highlighting of voltage-magnitude violations (undervoltage / overvoltage)
- Solver page with adjustable tolerance / iteration limit and a convergence log
- Reports page with a results table, a voltage-profile chart, and CSV export
- Open / Save / New file workflow with input validation and clear error messages
- Graceful handling of unsolvable or extreme operating points, with a clear
  non-convergence warning instead of a crash
- Targets a single-file portable Windows executable

## Status

Implemented through Sprint 7:

| Area | State |
|------|-------|
| Network file parser and validation | Done |
| Backward-Forward Sweep solver | Done |
| Single-line-diagram rendering | Done |
| On-the-fly equipment editor | Done |
| File management (Open / Save / New) | Done |
| Solver page and Reports page (table, chart, CSV) | Done |
| Robustness and graceful degradation | Done |
| Packaging, user manual, infographic | Planned (see `docs/SPRINT_PLAN.md`) |

The automated test suite (parser, solver, diagram, equipment editing, file I/O,
solver and reports views, robustness) currently has 69 passing tests.

## Quick Start (Development)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m gridlens
```

Requires Python 3.11 or newer. On launch the bundled example feeder
(`data/examples/4bus_radial.json`) is loaded and solved automatically, so the
diagram opens populated.

## Build Executable

```powershell
python build.py
```

Produces `dist/GridLens.exe` — a portable Windows 11 executable that runs without
a separate Python installation.

---

## User Manual

A full user manual is built into the application: click the **?** button in
the top-right corner to open it on the Help page. The same content lives in
[`src/gridlens/ui/help/user_manual.md`](src/gridlens/ui/help/user_manual.md).

---

## Project Layout

```
src/gridlens/
  core/      VA solver, network model, file parser/validator
  ui/        PyQt6 frontend (shell, views, single-line-diagram items)
  utils/     Validators, constants
data/        Example networks, file-format spec
tests/       Headless pytest suite
docs/        Sprint plan, user-manual and infographic outlines
```

## Tech Stack

Python 3.11 · PyQt6 · numpy · matplotlib · PyInstaller
