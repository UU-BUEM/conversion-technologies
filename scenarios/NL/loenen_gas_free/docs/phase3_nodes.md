# Phase 3 — per-building node assembly

**Status: done for the 1,260-building single-dwelling scope.**

## What was built

`scenarios/NL/loenen_gas_free/scripts/build_nodes.py` — new, scenario-only
glue (not part of the `conversion_technologies` package; this package
deliberately has no `nodes:`/demand concept, see
`docs/calliope_schema_mapping.md` "occupancy is out of scope"). It:

1. Reads Phase 1's hourly parquet (`Q_heat_kW`, `dhw_kW`, `elec_kW` per
   building per hour) and combines `Q_heat_kW + dhw_kW` into one `heat_kW`
   series per building — both are the `heat` carrier this repo's
   boiler/heat-pump/CHP technologies already output, so DHW doesn't need
   its own carrier or technology.
2. Pivots to two wide-format CSVs (`demand_heat.csv`/`demand_elec.csv`,
   8,760 rows × 1,260 columns each, one column per building) — matching
   the `data_tables` shape Calliope's docs describe and this repo's own
   `weather_cop.py` already uses for a per-tech timeseries.
3. Writes `demand_techs.yaml` (two generic `demand` techs, `carrier_in:
   heat`/`electricity`), `nodes.yaml` (one node per building, each listing
   both demand techs plus all 5 non-gas household-scale technologies from
   Phase 2), and `data_tables.yaml` (wiring the two CSVs in as
   `sink_use_equals` via `add_dims`).

Real run against the actual 1,260-building Phase 1 output: **1,260 nodes
written**, both CSVs exactly 8,760×1,260 as expected. Spot-checked
`nodes.yaml`'s first two nodes and both CSVs' headers/first data row by
hand — real building ids, real demand values, correct tech list per node.

## Decision confirmed with real data: no cooking carrier needed

`constraints.md` #0 flagged `cooking_gas_kWh` as a possible second gas
end-use needing attention. Checked directly against the full 1,260-building
hourly output before deciding: **`cooking_gas_kW` sums to exactly 0 for
all 1,260 buildings** — every building in this population cooks
electrically (already inside `elec_kW`, per `ModelBUEM`'s own
double-counting guard). So v1 of this scenario models only two demand
carriers (heat, electricity), not three — a confirmed finding, not an
assumption carried over from the constraint note.

## `model.yaml` assembled

`scenarios/NL/loenen_gas_free/model.yaml` ties Phase 2's tech catalog +
Phase 3's nodes/demand/data_tables together into one importable Calliope
model definition. Two things flagged as **not verified against a running
Calliope install** (consistent with this repo's own standing caveat on
`additional_math.yaml`, `docs/calliope_schema_mapping.md`):

- `config.init.additional_math` is where `additional_math.yaml` should be
  wired in, per general Calliope 0.7 convention — not inside the plain
  `import:` list the techs/nodes/data_tables files use. Double-check this
  key against whatever exact `0.7.0.devN` build is actually pinned before
  solving.
- The `data_tables` `columns: nodes` + `add_dims: {techs: ..., parameters:
  sink_use_equals}` shape is Calliope's documented pattern applied by
  inference, not confirmed against output from a real solve — same caveat
  this repo's own `ratio_math.py`/`weather_cop.py` already carry.

## Known gaps carried forward from Phase 1, not re-solved here

- **75 multi-unit buildings still excluded** — `nodes.yaml` only covers
  the 1,260 single-dwelling buildings. Adding them needs a decision on
  whether a multi-unit building becomes one node (lumped demand, shared
  technology) or several (per-dwelling disaggregation of `buem`'s
  building-level output) — not taken yet.
- **Household-scale technologies only.** Every node gets the 5
  household-scale non-gas techs; `building`/`community`-scale variants
  from Phase 2's export aren't referenced anywhere in `nodes.yaml` — correct
  for single-dwelling buildings, but means shared/community infrastructure
  (e.g. one neighborhood-scale heat pump serving several nodes) isn't
  modeled at all in this version. Flag for a v2 if the scenario needs it.
- **No electricity grid capacity constraint per node/feeder** — unchanged
  from `constraints.md` #5 (`enerplanet-pylovo` not wired in).

## Next (Phase 4)

Submit `model.yaml` (plus its `import:`ed files) to `enerplanet/MEME`
(`?target=calliope`) or a local Calliope 0.7 install, and see whether it
actually solves — the real test of everything flagged above as
"not verified."
