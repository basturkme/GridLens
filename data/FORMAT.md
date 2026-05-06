# Network File Format (intermediate JSON)

This is the intermediate schema GridLens uses internally. When the
course-provided file format spec arrives, the parser will gain an
adapter that converts it into the same `Network` model — the rest of
the application (solver, UI) is unaffected.

## Top-level

```json
{
  "name": "4-bus radial example",
  "base_mva": 10.0,
  "buses": [...],
  "lines": [...],
  "loads": [...],
  "generators": [...],
  "capacitors": [...]
}
```

## Bus

| Field      | Type    | Notes                                            |
|------------|---------|--------------------------------------------------|
| id         | string  | Unique identifier                                |
| name       | string  | Human-readable label (optional)                  |
| base_kv    | number  | Nominal line-to-line voltage in kV               |
| is_slack   | boolean | Exactly one bus must be the slack/source         |
| is_leaf    | boolean | True for radial leaves where operator pins V    |
| v_set_pu   | number  | Operator-pinned magnitude (only if `is_leaf`)    |

## Line (branch)

| Field     | Type   | Notes                                  |
|-----------|--------|----------------------------------------|
| id        | string | Unique identifier                      |
| from_bus  | string | Source bus id                          |
| to_bus    | string | Destination bus id                     |
| r_pu      | number | Series resistance, per-unit            |
| x_pu      | number | Series reactance, per-unit             |
| b_pu      | number | Total shunt susceptance, per-unit      |
| rating_a  | number | Optional thermal rating in amperes     |

## Load / Generator

```json
{ "id": "L1", "bus": "B2", "p_kw": 250.0, "q_kvar": 80.0 }
```

## Capacitor (shunt compensation)

```json
{ "id": "C1", "bus": "B3", "q_kvar": 100.0, "in_service": true }
```

## Constraints

- The graph `(buses, lines)` must be a **tree** (radial — no loops).
- At most **10 buses** (per project specification).
- Exactly one bus has `is_slack: true`.
