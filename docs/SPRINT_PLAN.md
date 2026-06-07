# GridLens — Sprint Plan

Development roadmap for the EE 374 term project (distribution-feeder analyzer).
Each sprint is a self-contained, testable increment. Completed sprints list the
commit(s) that delivered them; planned sprints list their target scope.

Project grading (for prioritization):
**Computational Accuracy 40% · UI/UX Design 30% · Professionalism & Customer Satisfaction 30%**

Final deliverables (zip): the `.exe`, source code as PDF, a ≤7-page user
manual, and a one-page infographic.

---

## Status overview

| Sprint | Title | Status | Commit(s) |
|:------:|-------|:------:|-----------|
| 0 | Project scaffold | ✅ Done | `8cdbbee` |
| 1 | Network file parser + validation | ✅ Done | `3d715ec` |
| 2 | BFS power-flow solver | ✅ Done | `3d715ec` |
| 3 | Single-line-diagram rendering | ✅ Done | `f42a05f`, `de4112e` |
| 4 | On-the-fly equipment editor | ✅ Done | `4b37492` |
| 5 | File management (Open / Save / New) | ✅ Done | `1f5adb7` |
| 6 | Solver view + Reports view | ✅ Done | `f3d40ec` |
| 7 | Robustness & UX hardening | ✅ Done | — |
| 8 | Portable `.exe` packaging | ✅ Done | — |
| 9 | User manual + infographic + source PDF | ✅ Done | — |
| 10 | Course data format + solver corrections | ✅ Done | — |

Current test suite: **79 passing** (parser incl. course format, solver, SLD,
equipment, file I/O, solver/reports views, robustness).

---

## Completed sprints

### Sprint 0 — Project scaffold ✅
**Goal:** establish the architecture so later sprints drop into known slots.
- Package layout (`core` / `ui` / `utils`), dataclass network model, solver &
  parser stubs, Gridscale-X-style PyQt6 shell (header, sidebar, stacked views,
  footer), QSS theme, `_MEIPASS`-aware resource helper, PyInstaller spec.

### Sprint 1 — Network file parser + validation ✅
**Goal:** load a feeder from disk into the `Network` model, safely.
- `load_network` / `save_network` for the `data/FORMAT.md` JSON schema.
- Strict, well-located type errors; rejects bool-as-number.
- `validate_network`: ≤10 buses, exactly one slack, unique ids, resolvable
  references, pinned voltage only on leaf buses, connected **radial tree**
  (lines == buses-1 + reachability sweep). Loss-free round-trip.

### Sprint 2 — BFS power-flow solver ✅
**Goal:** resolve bus voltage magnitudes/angles (the 40% accuracy core).
- Backward-forward sweep (current summation) over the radial tree.
- Loads = PQ draw, generators = PQ injection, capacitors + line charging =
  shunt susceptance (in-service cap raises voltage).
- Outer Q-compensation loop holds the operator-pinned leaf voltage via
  `ΔQ ≈ ΔV / X_th`. Per-bus under/over/ok violation flags.
- Independent Kirchhoff-current residual test (<1e-7) validates accuracy.

> **Revised in Sprint 10:** the solver now uses **power (VA) summation** with
> adaptive under-relaxation, and holds a pinned leaf by **solving for the slack
> voltage** (the grid voltage changes; no reactive power is injected).

### Sprint 3 — Single-line-diagram rendering ✅
**Goal:** visualize the feeder so a field engineer can read it (Figure 1).
- Custom `QGraphicsItem`s: bus bars, branches, transformer (drawn at base-kV
  changes), load/generator/capacitor symbols, "Power Grid" source block.
- Radial tidy-tree layout; voltage-violation tinting; tooltips; wheel zoom.
- `NetworkView`: category tree, name/id filter, tree ↔ canvas selection sync.
- App startup loads + solves the bundled example so the canvas opens populated.

### Sprint 4 — On-the-fly equipment editor ✅
**Goal:** edit operating conditions live (project requirement vi).
- `EquipmentView`: pick an item → validated form. Editable: load P/Q,
  generator P/Q, capacitor Q + **in-service** toggle, **leaf bus pinned voltage**.
- Edits mutate the model and emit `networkEdited`; the shell re-solves and
  refreshes the SLD + live `|V|` readout + status bar instantly.
- Invalid input shows a red field and never corrupts the model.

### Sprint 5 — File management (Open / Save / New) ✅
**Goal:** turn the demo-only loader into a real document workflow.
- File menu (New / Open / Save / Save As / Reload Example) with standard
  shortcuts; Home-page buttons wired through signals.
- Dialog-free, unit-testable core ops (`open_path`, `save_to`, `new_network`,
  `load_startup_example`); `QFileDialog` wrappers with `QMessageBox` errors that
  reuse the `ParserError` text.
- Dirty-state tracking, title-bar file name + `[*]` modified marker, and a
  Save/Discard/Cancel guard on New/Open/Reload/Close.

### Sprint 6 — Solver view + Reports view ✅
**Goal:** make results first-class, beyond the SLD tint.
- **SolverView:** "Run Power Flow" with tolerance / max-iteration controls and a
  convergence log (status, iterations, mismatch, violations, lowest |V|); the
  chosen parameters also drive subsequent live re-solves.
- **ReportsView:** results table (bus, |V| pu, angle°, |V| kV, status) with
  violation colouring, a matplotlib voltage-profile chart with band lines, and
  CSV export.
- The shell distributes each solution to network / equipment / solver / reports.

### Sprint 7 — Robustness & UX hardening ✅
**Goal:** behave like a product under bad input and edge cases (Professionalism 30%).
- Solver no longer raises on pathological operating points: a sweep that
  collapses to zero, goes non-finite, or runs away (|V| > 1000 pu) returns
  `converged=False` with a clear reason (diverged / iteration-limit / pinned-not-held);
  non-finite voltages report as NaN.
- Network page shows a red non-convergence warning banner carrying the solver
  message; the status bar mirrors it.
- Edge cases (single-bus, no-load, extreme edits through the editor) handled
  without crashing; broadened unhappy-path tests.

---

### Sprint 8 — Portable `.exe` packaging ✅
**Goal:** ship a single Windows-11 portable executable (requirement viii).
- `python build.py` drives `gridlens.spec`; **all** example feeders, `FORMAT.md`,
  QSS and image assets are bundled and resolved through `_resources`.
- Windows `.exe` icon wired in the spec (`app.ico`); no UPX / excluded toolkits
  to limit Defender false positives.

### Sprint 9 — User manual + infographic + source PDF ✅
**Goal:** the written deliverables (Professionalism 30%).
- **User manual** built into the app (Help page), rewritten for the course data
  format and current behaviour.
- **Infographic** — a single-page, brand-styled document (hero + spec/feature
  blocks) for the submission.
- **Source-code PDF** of the core engine for the submission.

### Sprint 10 — Course data format + solver corrections ✅
**Goal:** match the instructor-provided file format and clarified solver semantics.
- **Parser** now reads/writes the course JSON (`system_data`, `bus_data`,
  `load_data`, `gen_data`, `shunt_data`, `line_data`, `transformer_data`):
  ohms→pu conversion, transformers folded into the branch list, shunt sign per
  spec (positive `q_mvar` = reactor), loads/gens carry a nameplate while the
  operating P/Q (and power factor) are entered by hand — never assumed. Leaves
  are auto-detected; `gen_id` and `generator_id` are both accepted.
- **Solver** switched to **VA / power-summation** sweep with adaptive
  under-relaxation; `max_iter` is a firm *total* budget; a pinned leaf is held by
  **solving for the slack voltage** (no Q injection).
- **UX:** non-convergence banner on every page; live power-factor readout and
  rated-S display in the editor; transformer category; network-named CSV export;
  redesigned Home (hero + feature cards); visible input fields; app icon.
- New example feeders: `example_network` (course), `11bus_radial`,
  `15bus_example_network`, `15bus_example_network_stressed`.

---

## Conventions
- Every code sprint ships with headless (`QT_QPA_PLATFORM=offscreen`) or pure
  unit tests; keep the suite green.
- Pure logic stays in `core` (no Qt); Qt stays in `ui`.
- One sprint → one (or few) focused commit(s); messages describe the increment.
