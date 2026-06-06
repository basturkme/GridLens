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

- The folder (Open) icon at the top right, or Ctrl+O, then choose a `.json` file.
- On the Home page, click "Open Network File...".
- "Load Example Feeder" (Home page) or File > Reload Example returns to the
  built-in example at any time. Other bundled examples can be opened from the
  Open dialog, which starts in the examples folder.

If a file is malformed or is not a valid radial network, GridLens shows a
message describing the problem (for example, a missing slack bus, a duplicate
identifier, or a loop in the topology) and keeps the network you already had
open.

### Input data format

A network is a JSON file using the standard course format: one object with the
sections `system_data`, `bus_data`, `load_data`, `gen_data`, `shunt_data`,
`line_data`, and `transformer_data`. Identifiers are integers. A short example:

```json
{
  "system_data": [
    { "network_name": "Example Network", "s_base_mva": 1, "slack_bus": 1 }
  ],
  "bus_data": [
    { "bus_id": 1, "bus_name": "Bus 1", "voltage_level_kv": 35 },
    { "bus_id": 4, "bus_name": "Bus 4", "voltage_level_kv": 0.4 }
  ],
  "load_data":  [ { "load_id": 1, "bus_id": 4, "s_rated_mva": 1 } ],
  "gen_data":   [ { "gen_id": 1, "bus_id": 2, "s_rated_mva": 1 } ],
  "shunt_data": [ { "shunt_id": 1, "bus_id": 3, "q_mvar": 0.2 } ],
  "line_data":  [ { "line_id": 1, "from_bus_id": 2, "to_bus_id": 3, "r_ohm": 1, "x_ohm": 2.5 } ],
  "transformer_data": [
    { "transformer_id": 1, "hv_bus_id": 1, "lv_bus_id": 2,
      "v_rated_high_kv": 35, "v_rated_low_kv": 0.4, "rated_s_mva": 2, "x_pu": 0.05 }
  ]
}
```

Things worth knowing about the format:

- **Lines** are given in **ohms** (`r_ohm`, `x_ohm`); GridLens converts them to
  per-unit internally on the system base.
- **Transformers** are a separate section, modelled by their reactance `x_pu`
  (on the transformer's own MVA base).
- **Shunt sign:** a positive `q_mvar` is a **reactor** (absorbs reactive power),
  a negative `q_mvar` is a **capacitor** (supplies it).
- **Loads and generators** carry only a nameplate `s_rated_mva`. Their actual
  operating point — active power P, reactive power Q, and therefore the power
  factor — is the real-time state you enter by hand on the Equipment page; it is
  not assumed. (Power factor is never assumed to be 1.)
- The **leaf** buses (feeder ends where you may pin a voltage) are detected
  automatically from the topology; they are not flagged in the file.

Rules enforced on load: the network must be radial (a tree, every bus reachable
from the source, no loops); exactly one slack bus is named in `system_data`; and
all identifiers are unique with every reference pointing at a bus that exists.

## 3. Reading the single-line diagram

Open the Network page. The diagram is drawn left to right, from the source:

- A vertical bar is a bus. Its label shows the bus name; below it the solved
  voltage magnitude (per unit) and angle appear once a solution exists.
- The block on the far left labelled "Power Grid" is the slack source.
- Two interlocking circles mark a transformer.
- A downward arrow is a load; a circled wave is a generator; a two-plate symbol
  is a capacitor and a coil symbol is a reactor. A unit switched out of service
  is greyed out.

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

- **Load:** active power P (kW) and reactive power Q (kvar). The resulting
  **power factor** is shown live beneath them (e.g. `0.949 lagging`), and the
  nameplate rating is shown for reference.
- **Generator:** active power P (kW) and reactive power Q (kvar), with the same
  live power-factor readout.
- **Capacitor / reactor:** rating Q (kvar) and the **In service** switch.
- **Leaf bus:** tick "Hold this voltage" and enter a per-unit magnitude to pin
  the leaf voltage; untick it to let the voltage float with the load. When a leaf
  is pinned, GridLens holds it at your set-point and the **grid (slack) voltage
  becomes the result** — it changes to whatever value supplies the feeder; no
  reactive power is injected to do this.

Numeric fields validate as you type. Invalid or out-of-range input turns the
field red with a tooltip and is not applied until corrected. Line and transformer
parameters are fixed network data and are read-only.

## 5. Running the solver

GridLens solves with the **VA (power-summation backward-forward sweep)** method,
which exploits the radial structure for fast, reliable convergence. The solver
runs automatically when a network is loaded and after every edit, so you usually
do not need to trigger it manually. The Solver page gives manual control:

- Adjust **Tolerance** (per unit) and **Max iterations**, then click
  "Run Power Flow".
- A loose tolerance converges in fewer iterations but is less accurate; for
  precise voltages keep the default tolerance. Max iterations is a firm limit on
  the total number of sweeps — the solver never exceeds it.
- The convergence log reports whether the solve converged, the iteration count,
  the final mismatch, the number of violations, and the lowest bus voltage. When
  a leaf is pinned, it also reports the grid voltage required to hold it.
- The iteration table lists each sweep and its voltage change; "Clear history"
  empties the log and table.

## 6. Reports and export

The Reports page shows the latest solution two ways:

- A results table: every bus with its voltage magnitude (per unit and in kV),
  angle, and status; out-of-band buses are coloured.
- A voltage-profile chart of |V| across the feeder, with dashed lines marking
  the allowed band.
- "Export CSV" saves the table to a file. The suggested file name is built from
  the network name (e.g. `Example_Network_voltages.csv`).

## 7. Interpreting the results

- The status bar summarises the last solve: iterations and the number of buses
  with a voltage violation.
- On the diagram, any non-green bus is out of band. Blue means the voltage has
  sagged too low (often far from the source under heavy load); red means it is
  too high (often light load with capacitors or generation in service).
- Typical workflow: load the feeder, enter the operating loads, look for blue or
  red buses, then on the Equipment page reduce a load, switch a capacitor in, or
  adjust generation, and watch the colours and voltages update until every bus is
  green.
- If the operating point is beyond what the feeder can supply, the power flow
  cannot converge. GridLens does not crash: a red **"did not converge" banner
  appears on every page** and the status bar says so. The voltages shown after a
  non-converged solve are not a valid result — reduce the load (or relax the
  pinned voltage) until it converges.

## 8. Saving your work

- File > Save (Ctrl+S) writes back to the current file.
- File > Save As... (Ctrl+Shift+S) writes to a new file.
- File > New (Ctrl+N) clears the workspace.

Saved files are written in the same course JSON format, with the operating P/Q
you entered preserved so your work reloads exactly.

The window title shows the current file name; an asterisk appears when there are
unsaved changes. If you try to open another file, start a new one, or close the
window with unsaved changes, GridLens asks whether to save first.

Note: the built-in example is read-only by design. After editing it, Save routes
you to Save As so you choose a new file rather than overwriting the shipped
example.
