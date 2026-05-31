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
- Open / Save / New file workflow with input validation and clear error messages
- Targets a single-file portable Windows executable

## Status

Implemented through Sprint 5:

| Area | State |
|------|-------|
| Network file parser and validation | Done |
| Backward-Forward Sweep solver | Done |
| Single-line-diagram rendering | Done |
| On-the-fly equipment editor | Done |
| File management (Open / Save / New) | Done |
| Solver and Reports views, packaging, manual/infographic | Planned (see `docs/SPRINT_PLAN.md`) |

The automated test suite (parser, solver, diagram, equipment editing, file I/O)
currently has 54 passing tests.

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

# User Manual

This manual explains how to operate GridLens. No power-systems theory is
required to use the tool.

## 1. Launching the application

- Development: run `python -m gridlens` from an activated virtual environment.
- Packaged: double-click `GridLens.exe`. No installation is needed.

When GridLens starts it loads and solves a built-in example feeder so you can
see the interface working immediately. The left sidebar switches between pages;
the status bar at the bottom reports the current network, how many iterations
the solver took, and how many voltage violations were found.

## 2. Loading a network

You can load a feeder in three ways:

- File menu > Open... (Ctrl+O), then choose a `.json` network file.
- On the Home page, click "Open Network File...".
- File menu > Reload Example (or the Home page "Load Example Feeder" button) to
  return to the bundled example at any time.

If a file is malformed or is not a valid radial network, GridLens shows a
message describing the problem (for example, a missing slack bus, a duplicate
identifier, or a loop in the topology) and keeps the network you already had
open.

### Input data format

A network is a JSON file with five lists: `buses`, `lines`, `loads`,
`generators`, and `capacitors`. The full schema is documented in
`data/FORMAT.md`. A minimal example:

```json
{
  "name": "4-bus radial example",
  "base_mva": 10.0,
  "buses": [
    { "id": "B1", "name": "Bus 1", "base_kv": 33.0, "is_slack": true,  "is_leaf": false },
    { "id": "B4", "name": "Bus 4", "base_kv": 11.0, "is_slack": false, "is_leaf": true, "v_set_pu": 1.00 }
  ],
  "lines":      [ { "id": "L34", "from_bus": "B3", "to_bus": "B4", "r_pu": 0.025, "x_pu": 0.07 } ],
  "loads":      [ { "id": "Ld4", "bus": "B4", "p_kw": 150.0, "q_kvar": 50.0 } ],
  "generators": [ { "id": "G2",  "bus": "B2", "p_kw": 100.0, "q_kvar": 0.0 } ],
  "capacitors": [ { "id": "C3",  "bus": "B3", "q_kvar": 50.0, "in_service": true } ]
}
```

Rules GridLens enforces when loading:

- The network must be radial (a tree): exactly one fewer line than buses, with
  no loops, and every bus reachable from the source.
- Exactly one bus is the slack/source (`is_slack: true`).
- At most 10 buses.
- Identifiers are unique, and every load/generator/capacitor/line refers to a
  bus that exists.
- A pinned voltage (`v_set_pu`) may only be set on a leaf bus.

## 3. Reading the single-line diagram

Open the Network page from the sidebar. The diagram is drawn left to right,
starting from the source:

- A vertical bar is a bus. Its label shows the bus name; below it the solved
  voltage magnitude (per unit) and angle are shown once a solution exists.
- The block on the far left labelled "Power Grid" is the slack source.
- Two interlocking circles on a line mark a transformer (drawn wherever the two
  buses it connects have different base voltages).
- A downward arrow is a load; a circled wave is a generator; a two-plate symbol
  is a capacitor bank. A capacitor that is switched out of service is greyed out.

Bus colour indicates the voltage result:

- Green: voltage within the allowed band.
- Blue: undervoltage (below the lower limit).
- Red: overvoltage (above the upper limit).

You can hover any item for details, click a bus to select it, scroll to zoom,
and use the filter box to find a bus by name or identifier. Selecting a bus in
the list highlights it on the diagram and vice versa.

## 4. Editing operating conditions

Open the Equipment page. Pick an item from the list on the left to edit it on
the right. Every accepted change is applied immediately: the network is
re-solved and the diagram, voltages, and status bar update at once.

You can edit:

- Load: active power P (kW) and reactive power Q (kvar).
- Generator: active power P (kW) and reactive power Q (kvar).
- Capacitor bank: rating Q (kvar) and the In service switch.
- Leaf bus: tick "Hold this voltage" and enter a per-unit magnitude to pin the
  leaf voltage; untick it to let the voltage float with the load.

Numeric fields validate as you type. If you enter something that is not a valid
number (or is out of range), the field turns red, a tooltip explains why, and
the value is not applied until it is corrected. Line parameters (R, X, B) are
fixed network data and are shown read-only.

## 5. Interpreting the results

- The status bar summarises the last solve: number of iterations, and the count
  of buses with a voltage violation.
- On the diagram, any non-green bus is out of band. Blue means the voltage has
  sagged too low (commonly far from the source under heavy load); red means it
  is too high (commonly light load with capacitors or generation in service).
- A typical workflow: load the feeder, look for blue or red buses, then on the
  Equipment page reduce a load, switch a capacitor in, or adjust generation, and
  watch the colours and voltages update until every bus is green.

## 6. Saving your work

- File menu > Save (Ctrl+S) writes back to the current file.
- File menu > Save As... (Ctrl+Shift+S) writes to a new file.
- File menu > New (Ctrl+N) clears the workspace.

The window title shows the current file name; an asterisk appears when there are
unsaved changes. If you try to open another file, start a new one, or close the
window with unsaved changes, GridLens asks whether to save first.

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
