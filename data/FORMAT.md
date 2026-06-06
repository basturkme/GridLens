# Network File Format

GridLens reads and writes the course-provided JSON network format. A file is a
single JSON object with the sections below. Ids may be integers or strings.

```json
{
  "system_data": [ ... ],
  "bus_data": [ ... ],
  "load_data": [ ... ],
  "gen_data": [ ... ],
  "shunt_data": [ ... ],
  "line_data": [ ... ],
  "transformer_data": [ ... ]
}
```

## system_data (one entry)

| Field        | Type   | Notes                                  |
|--------------|--------|----------------------------------------|
| network_name | string | Display name                           |
| s_base_mva   | number | System apparent-power base, MVA        |
| slack_bus    | id     | Id of the slack / source bus           |

## bus_data

| Field            | Type   | Notes                                          |
|------------------|--------|------------------------------------------------|
| bus_id           | id     | Unique identifier                              |
| bus_name         | string | Human-readable label (optional)                |
| voltage_level_kv | number | Nominal line-to-line voltage in kV             |
| v_set_pu         | number | *Optional.* Operator-pinned magnitude; only meaningful on a leaf bus. Our app writes this when the operator pins a leaf voltage. |

The slack bus is named in `system_data.slack_bus`. **Leaf** buses (a feeder end
where the operator may pin a voltage, e.g. Bus 4) are detected automatically as
the non-slack buses with a single branch — they are not flagged in the file.

## line_data

| Field       | Type | Notes                                      |
|-------------|------|--------------------------------------------|
| line_id     | id   | Unique identifier                          |
| from_bus_id | id   | Source bus id                              |
| to_bus_id   | id   | Destination bus id                         |
| r_ohm       | number | Series resistance in **ohms/phase**      |
| x_ohm       | number | Series reactance in **ohms/phase**       |

Impedances are converted to per-unit internally with `Z_base = kV² / S_base`
(the line's voltage level).

## transformer_data

| Field           | Type   | Notes                                       |
|-----------------|--------|---------------------------------------------|
| transformer_id  | id     | Unique identifier                           |
| hv_bus_id       | id     | High-voltage side bus                       |
| lv_bus_id       | id     | Low-voltage side bus                        |
| v_rated_high_kv | number | HV rated voltage, kV                        |
| v_rated_low_kv  | number | LV rated voltage, kV                        |
| rated_s_mva     | number | Transformer rated power, MVA                |
| x_pu            | number | Reactance on the transformer's own MVA base |

A transformer is treated as a branch; its `x_pu` is referred to the system base
(`x_pu · S_base / rated_s_mva`).

## load_data / gen_data

| Field                  | Type | Notes                                       |
|------------------------|------|---------------------------------------------|
| load_id / gen_id       | id   | Unique identifier (`generator_id` also accepted) |
| bus_id                 | id   | Bus the unit connects to                    |
| s_rated_mva            | number | Nameplate apparent-power rating, MVA      |
| p_mw                   | number | *Optional.* Operating active power, MW      |
| q_mvar                 | number | *Optional.* Operating reactive power, MVAr  |

The **operating point** (active/reactive power, and hence power factor) is the
real-time state, entered by hand in the app — power factor is never assumed. The
course files carry only `s_rated_mva`; the operating P/Q then default to zero
until set. GridLens additionally writes `p_mw`/`q_mvar` when it saves, so edited
operating conditions round-trip.

## shunt_data (compensation)

| Field      | Type    | Notes                                            |
|------------|---------|--------------------------------------------------|
| shunt_id   | id      | Unique identifier                                |
| bus_id     | id      | Bus the shunt connects to                        |
| q_mvar     | number  | Reactive power **absorbed**: `> 0` reactor (inductive), `< 0` capacitor (supplies reactive). |
| in_service | boolean | *Optional, default true.* Toggled on the fly.    |

Multiple shunts may sit on the same bus.

## Constraints

- The graph (buses + lines + transformers) must be a **tree** (radial — no loops):
  exactly `buses − 1` branches, all reachable from the slack.
- Exactly one slack bus, named in `system_data`.
- Unique ids within each section.
