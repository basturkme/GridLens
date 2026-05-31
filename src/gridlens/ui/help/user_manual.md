# GridLens User Manual

GridLens is a distribution-feeder analyzer for radial, three-phase, balanced
networks. It turns a fixed feeder topology plus the current operating conditions
into immediate visibility of every bus voltage, and highlights any bus that is
out of its allowed voltage band. No power-systems theory is required to use it.

## 1. Launching

- Packaged: double-click `GridLens.exe`. No installation is needed.
- Development: run `python -m gridlens`.

On start, GridLens loads and solves a built-in example feeder so the interface
is populated immediately. The left sidebar switches between pages; the status
bar at the bottom reports the current network, how many iterations the solver
took, and how many voltage violations were found.

## 2. Loading a network

You can load a feeder in three ways:

- File menu > Open... (Ctrl+O), then choose a network `.json` file.
- On the Home page, click "Open Network File...".
- File menu > Reload Example (or the Home page "Load Example Feeder" button) to
  return to the built-in example at any time.

If a file is malformed or is not a valid radial network, GridLens shows a
message describing the problem (for example, a missing slack bus, a duplicate
identifier, or a loop in the topology) and keeps the network you already had
open.

### Input data format

A network is a JSON file with five lists: `buses`, `lines`, `loads`,
`generators`, and `capacitors`. A minimal example:

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

Rules enforced on load:

- The network must be radial (a tree): exactly one fewer line than buses, with
  no loops, and every bus reachable from the source.
- Exactly one bus is the slack/source (`is_slack: true`).
- At most 10 buses.
- Identifiers are unique, and every load/generator/capacitor/line refers to a
  bus that exists.
- A pinned voltage (`v_set_pu`) may only be set on a leaf bus.

## 3. Reading the single-line diagram

Open the Network page. The diagram is drawn left to right, from the source:

- A vertical bar is a bus. Its label shows the bus name; below it the solved
  voltage magnitude (per unit) and angle appear once a solution exists.
- The block on the far left labelled "Power Grid" is the slack source.
- Two interlocking circles on a line mark a transformer (drawn wherever the two
  buses it connects have different base voltages).
- A downward arrow is a load; a circled wave is a generator; a two-plate symbol
  is a capacitor bank. A capacitor switched out of service is greyed out.

Bus colour shows the voltage result: green = within band, blue = undervoltage,
red = overvoltage.

You can hover any item for details, scroll to zoom, and use the filter box to
find a bus by name or identifier. Clicking a bus or an equipment symbol opens
that item directly in the Equipment editor.

## 4. Editing operating conditions

Open the Equipment page (or click an item on the diagram). Pick an item on the
left to edit it on the right. Every accepted change is applied immediately: the
network is re-solved and the diagram, voltages, and status bar update at once.

You can edit:

- Load: active power P (kW) and reactive power Q (kvar).
- Generator: active power P (kW) and reactive power Q (kvar).
- Capacitor bank: rating Q (kvar) and the In service switch.
- Leaf bus: tick "Hold this voltage" and enter a per-unit magnitude to pin the
  leaf voltage; untick it to let the voltage float with the load.

Numeric fields validate as you type. Invalid or out-of-range input turns the
field red with a tooltip and is not applied until corrected. Line parameters
(R, X, B) are fixed network data and are read-only.

## 5. Running the solver

The solver runs automatically when a network is loaded and after every edit, so
you usually do not need to trigger it manually. The Solver page gives manual
control:

- Adjust Tolerance (per unit) and Max iterations, then click "Run Power Flow".
- A loose tolerance converges in fewer iterations but is less accurate; for
  precise voltages keep the default tolerance. The tolerance and iteration limit
  you set here are also used by the automatic re-solves after edits.
- The convergence log reports whether the solve converged, the iteration count,
  the final mismatch, the number of violations, and the lowest bus voltage.

## 6. Reports and export

The Reports page shows the latest solution two ways:

- A results table: every bus with its voltage magnitude (per unit and in kV),
  angle, and status; out-of-band buses are coloured.
- A voltage-profile chart of |V| across the feeder, with dashed lines marking
  the allowed band.
- "Export CSV" saves the table to a file for a report or spreadsheet.

## 7. Interpreting the results

- The status bar summarises the last solve: iterations and the number of buses
  with a voltage violation.
- On the diagram, any non-green bus is out of band. Blue means the voltage has
  sagged too low (often far from the source under heavy load); red means it is
  too high (often light load with capacitors or generation in service).
- Typical workflow: load the feeder, look for blue or red buses, then on the
  Equipment page reduce a load, switch a capacitor in, or adjust generation, and
  watch the colours and voltages update until every bus is green.
- If the operating point is beyond what the feeder can supply, the solver cannot
  converge. GridLens does not crash: a red warning banner appears on the Network
  page and the status bar explains that the power flow did not converge. Reduce
  the load (or relax the pinned voltage) and the solution recovers.

## 8. Saving your work

- File menu > Save (Ctrl+S) writes back to the current file.
- File menu > Save As... (Ctrl+Shift+S) writes to a new file.
- File menu > New (Ctrl+N) clears the workspace.

The window title shows the current file name; an asterisk appears when there are
unsaved changes. If you try to open another file, start a new one, or close the
window with unsaved changes, GridLens asks whether to save first.

Note: the built-in example is read-only by design. After editing it, Save routes
you to Save As so you choose a new file rather than overwriting the shipped
example.
