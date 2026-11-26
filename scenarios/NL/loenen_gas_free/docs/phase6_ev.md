# Phase 6 — electric vehicles in the Loenen scenario

**Status: wired; full 1,260-building solves done (flat price smart,
day-ahead price smart and uncontrolled), all buildings solved, re-run
2026-11-24 after the buem alignment fix and with the EV battery starting
and ending at the simulated car's levels; results in "Full runs" below.** EV technologies come from this repo's `ev` category
(`docs/calliope_schema_mapping.md` "Electric vehicles"); the household EV
behaviour comes from the occupancy package's EV model
(`occupancy/docs/ev/design.md`), via buem.

## Data: Phase 1 rerun with EVs

```text
python scenarios/NL/loenen_gas_free/scripts/run_demand_with_cooling_setpoint.py \
    --buem-root D:/test/buem --cooling-setpoint 26 --workers 16 \
    --ev-ownership-probability 0.2 \
    --output scenarios/NL/loenen_gas_free/data/loenen_single_dwelling_hourly_cool26_ev20.parquet \
    --summary-output scenarios/NL/loenen_gas_free/data/loenen_single_dwelling_summary_cool26_ev20.parquet
```

(`buem_env`.) Each household owns an EV with probability 0.2, the Loenen
community default (above the ~6% national share of plug-in cars), drawn
per building from its own seed. New hourly columns:

| Column | Meaning | Used as |
| --- | --- | --- |
| `ev_kW` | Home charging, uncontrolled (charge on plug-in), grid side | `demand_ev_uncontrolled` (baseline variant); its peak fixes the wallbox size |
| `ev_plugged_in` | Share of the hour the car is connected at home | `flow_out_max_relative` of the charger (and V2G) |
| `ev_drive_kW` | Battery energy used for driving | `demand_ev_driving` `sink_use_equals` |
| `ev_away_kW` | Grid-side energy charged away from home | x DC charger efficiency -> `supply_ev_away` `source_use_equals` |
| `ev_stored_kWh` | Battery energy at the end of the hour | battery start level (`storage_initial`) and end level (`storage_final_min`) |

`elec_kW` (appliances, buem's internal-gain `elecLoad`) excludes the EV.
Metered electricity = `elec_kW + ev_kW`.

**Rerun 2026-11-24 (buem alignment fix).** buem matched occupancy's
hourly series (labelled 00:00, 01:00, ...) to the weather (00:30,
01:30, ...) by the nearest label; pandas breaks that 30-minute tie towards
the later label, so every occupancy series (internal gains, appliances,
presence, hot water, EV) was one hour early, the year's first hour was
dropped and its last hour repeated. The repeated hour also broke the EV
balance: charging counted twice while the stored energy stayed flat,
which made smart charging draw 132 kWh less than uncontrolled. buem now
matches the hour both timestamps fall in. After the rerun every
occupancy column equals the old one moved one hour later; the EV balance
closes in every hour (largest residual 2.3e-6 kWh); heating -0.2%,
cooling -0.6%. Previous data: `*.before_align.parquet`.

Run 2026-11-23: 1,260/1,260 ok in about 13 minutes (16 workers).

| Figure | Value |
| --- | --- |
| Households with an EV | 264 (21%) |
| Home charging per EV, median (p10-p90) | 2,345 kWh/yr (2,180-2,530) |
| `elec_kW` per household, median | 2,935 kWh/yr (previous run 2,977) |
| Heating per household, median | 19,337 kWh/yr (previous run 22,120) |

**The heating drop is not the EV.** It comes from buem 6.5.0, released
after the `cool26` run, which takes the reference floor area from the BAG
register: median `A_ref` went from 206 to 136 m². On the 34 buildings
whose floor area did not change, heating moved by +0.1%, which is the
small effect of taking EV charging out of the internal gains. The `cool26`
files and `outputs/v3/` are kept unchanged for reference; new results
need a full re-solve.

## Wiring (`scripts/build_nodes.py`)

Only nodes whose household owns an EV get EV techs, all on the
`ev_electricity` carrier:

| Tech at an EV node | Setting |
| --- | --- |
| `ev_charger_ac_household` | `flow_cap_min = flow_cap_max` = the household's wallbox (peak `ev_kW` x 0.92, car side): an existing charger, not a sizing decision; `cost_flow_cap: 0` (sunk) |
| `ev_battery_household` | 60 kWh, 10% reserve. `cyclic_storage: false`; starts at the simulated car's level before the first hour (`storage_initial`, from `ev_stored_kWh`) and must end at least at its simulated level in the last hour, less 0.01 kWh (`storage_final_min`, custom constraint `storage_final_level_min`). occupancy's own year is then always feasible and smart charging describes the same car as uncontrolled. Never set `storage_initial` with `cyclic_storage: true`: Calliope then forces that exact level in the year's last hour, which made 48 households infeasible in the first full run. Without `ev_stored_kWh` in the data, `build_nodes.py` falls back to cyclic with a free start. |
| `demand_ev_driving` | driving energy |
| `supply_ev_away` | fixed away-charging energy, price 0 (`energy_prices.csv` note: a constant) |

Data tables `loenen_ev_availability`, `loenen_ev_driving`,
`loenen_ev_away` (CSV columns: EV nodes only). The technology export
(`technologies/export_config.json`) now includes the four EV techs; the
generated additional math carries the availability constraint
`flow_out_max_availability`.

## Variants (`solve_single_building.py` / `solve_all_buildings.py --ev`)

| `--ev` | EV node gets |
| --- | --- |
| `smart` (default) | the wiring above: the optimiser schedules charging within the plugged-in hours |
| `uncontrolled` | none of the above; `demand_ev_uncontrolled` = `ev_kW` on electricity (the baseline) |
| `v2g` | smart + `ev_v2g_household`, with the same availability table |
| `none` | no EV at all |

The single-building model keeps a data table only when its tech is at the
node and its CSV has the node's column, so the variants need no
per-table bookkeeping.

Per-building decomposition stays exact: the EV battery is node-local.

## Results (spot checks)

Full-year solves (2018 weather, heating and cooling, CBC, 30-45 s each),
2026-11-23. Full-population solves are still open.

| Building | `--ev` | Total cost, EUR/yr | Grid import, kWh/yr | EV checks |
| --- | --- | --- | --- | --- |
| bldg_10 | smart | 6,134.71 | 7,718 | 2,265 kWh charged (car side); 0 kWh while unplugged; 0 hours above cap x availability; battery min 6.0 kWh, start = end 54 kWh |
| bldg_10 | uncontrolled | 6,132.19 | 7,708 | 2,452 kWh EV demand (grid side) |
| bldg_10 | v2g | same as smart | 7,718 | V2G 0 kWh: the discharger is never bought at a flat price |
| bldg_1035, bldg_1050 | smart | 9,061.95; 7,056.45 | -- | same checks pass |
| bldg_8 (no EV) | smart | 6,136.36 | 7,642 | no EV techs, solves as before |

- **Smart vs. uncontrolled differ by EUR 2.52 (9.7 kWh).** The optimised
  battery must end the year where it started, while occupancy's
  uncontrolled year does not quite. With a flat price there is nothing
  else to gain.
- **Existing wallbox.** Its investment cost is zeroed at the node
  (`cost_flow_cap: 0`), because it exists in every variant. The first spot
  run charged it only in the smart variant, which made smart EUR 83.6/yr
  dearer than uncontrolled for the same charger.
- **V2G** stays unused until the price varies enough over the day to beat
  the round-trip losses, the battery-wear cost (EUR 0.046/kWh) and the
  discharger investment.

## Hourly grid price: NL day-ahead 2018

At the flat 0.26 EUR/kWh, smart and uncontrolled charging cost the same,
so the EV's flexibility has no value. `scripts/build_grid_price.py` adds
an hourly price:

- **Source.** The Netherlands day-ahead price for 2018 (the weather year),
  from the Energy-Charts API of Fraunhofer ISE, CC BY 4.0, data from the
  Bundesnetzagentur's SMARD.de. Mean 52.54 EUR/MWh, range 0.55-175, no
  gaps and no negative hours.
- **Level.** The hourly price is the sourced flat price plus the hour's
  deviation from the day-ahead mean: `0.26035 + (DA_t - 52.54) / 1000`
  EUR/kWh, ranging 0.208-0.383. The annual mean is unchanged, so costs
  stay comparable with the flat runs. Only the hourly shape is added, as a
  household on a dynamic contract sees it. Taxes stay excluded (system
  perspective, `constraints.md` 8).
- **Time alignment.** Day-ahead hours are UTC starts; the model's
  timesteps are UTC interval midpoints (HH:30), so hour HH:00 maps to
  HH:30.
- **Output.** `grid_price_nl_2018.csv` (scenario root, both the raw
  day-ahead price and the derived `cost_flow_out`).

`build_nodes.py --grid-price day_ahead` (the default since this change;
`flat` reproduces the earlier runs) writes it as a node-independent data
table (`loenen_grid_price`, no `columns`) and drops the scalar
`cost_flow_out` from `supply_grid_electricity`. A data table without
`columns` was checked against a per-node table on the scratch model: the
same cost to the last cent. The day-ahead node set is built into
`nodes_day_ahead/`, and the solve scripts take `--nodes-dir
nodes_day_ahead`. The flat-price `nodes/` stay as they were.

bldg_10, full year (heating and cooling), with the day-ahead price:

| `--ev` | Total cost, EUR/yr | Grid electricity cost, EUR/yr |
| --- | --- | --- |
| uncontrolled | 6,150.77 | 2,027.4 |
| smart | 6,105.31 | 1,982.0 |
| v2g | 6,105.31 (V2G not bought) | 1,982.0 |

- **Smart saves EUR 45.46/yr** on the same charged energy: about 0.019
  EUR per kWh, roughly 7% of the EV's charging cost.
- **V2G is still not worth buying.** The 2018 day-ahead spread is too
  small to beat its round-trip losses, battery wear and investment.
- **Battery throughput is not cycling.** With V2G available, the battery's
  reported throughput doubles at identical cost. The battery is lossless
  (efficiency 1.0, losses sit on the charger), so simultaneous charging and
  discharging is free and the solver may report it.

## Full runs (2026-11-24)

Three runs of 1,260 buildings each (heating and cooling), each 16 workers,
run one after another on the realigned Phase 1 data (1.65, 1.59 and
3.28 h; the flat run shared the machine with other jobs):

| Run | Output |
| --- | --- |
| flat price, smart | `outputs/v4/heating_and_cooling_ev_smart/` |
| day-ahead price, smart | `outputs/v4/day_ahead_ev_smart/` |
| day-ahead price, uncontrolled | `outputs/v4/day_ahead_ev_uncontrolled/` |

The flat-price uncontrolled run was skipped: at a flat price, smart and
uncontrolled differ only by the battery's end-of-year condition (EUR 2.52
for bldg_10). The flat smart run is the v4 reference for the heat
technologies on the new Phase 1 data.

Compare with `scripts/compare_ev_variants.py <smart.json>
<uncontrolled.json>` (per building, split into EV and non-EV buildings)
and `scripts/summarize_results.py`.

### Solving

Every run leaves a few CBC `-stop` timeouts from running 16 solvers at
once (`docs/phase5_per_building_decomposition.md` section 7: 1, 6 and 52
buildings here); `scripts/retry_failed.py` re-solves them with 4 workers.
Final state: **1,260/1,260 solved in all three runs.**

Earlier results are kept next to each run: `*.before_ev_fix.json` (first
pass: 48 EV buildings infeasible with `storage_initial` + cyclic),
`*.before_soc_fix.json` (cyclic battery with a free start),
`*.before_align.json` (exact start/end, but on the misaligned Phase 1
data).

### Results

| Figure | Flat, smart | Day-ahead, smart | Day-ahead, uncontrolled |
| --- | --- | --- | --- |
| Region annual cost, EUR M | 7.345 | 7.342 | 7.354 |
| Per building, median (P10-P90), EUR | 5,186 (2,931-9,592) | 5,182 (2,942-9,577) | 5,195 (2,942-9,587) |
| Grid electricity, MWh/yr | 9,549 | 9,731 | 9,731 |
| Grid electricity cost, kEUR/yr | 2,486.1 | 2,526.8 | 2,538.2 |
| Heat: biomass boiler / air HP / ground HP, MWh | 35,934 / 764 / 3,257 | 35,309 / 1,286 / 3,366 | same as smart |
| Buildings with air HP / ground HP | 196 / 240 | 183 / 244 | same as smart |
| EV home charging, car side, MWh | 571.1 | 571.1 | (on `electricity`) |
| EV away charging, MWh | 144.1 | 144.1 | (in the demand) |

**Smart vs. uncontrolled charging (day-ahead price):**

| Buildings | Cost, smart - uncontrolled |
| --- | --- |
| 264 with an EV | **-EUR 11,392/yr in total; per building median -43.20 (range -50.66 to -35.83)** |
| 996 without an EV | 0.00 for every building |

- The saving is about EUR 0.018 per grid-side kWh charged (620.8 MWh),
  roughly 7% of the EV's charging cost, on the same energy. EV charging
  differs by 2.9 kWh over the year: exactly the 0.01 kWh per car by
  which the battery may end below the simulated car's level. Region grid
  import differs by 14 kWh in all; the other 11 kWh is a shift between
  equally cheap heat options (about 35 kWh of heat from air heat pump to
  biomass boiler in a few EV buildings: the solver lands on a different
  optimum of equal cost).
- The heat technologies (sizes, buildings) are identical in both runs:
  EV flexibility does not change any building's heating or cooling
  choice.
- Before the buem alignment fix the saving was EUR 12,428 and EV charging
  differed by 127 kWh: occupancy's series were one hour early and the
  year's last hour was repeated, so the uncontrolled car charged twice in
  that hour.
- Non-EV buildings identical to the cent confirms the variants differ only
  at EV nodes.

**Flat vs. day-ahead price (smart):**

| Buildings | Cost, flat - day-ahead |
| --- | --- |
| 264 with an EV | +EUR 9,511/yr in total; per building median +31.95 (range 17.45 to 125.19) |
| 996 without an EV | -EUR 6,627/yr in total; per building median -9.98 (range -25.92 to 85.05) |

- Region cost is nearly unchanged (flat EUR 2.9 k higher), as intended:
  the day-ahead price keeps the flat annual mean.
- Households without an EV pay a little more under the hourly price,
  because their appliance load sits in the evening price peak. EV
  households pay less, because smart charging moves into cheap hours.
- The hourly price shifts heat towards heat pumps: air heat pump output
  +68% (764 to 1,286 MWh), biomass -625 MWh, grid import +182 MWh. The
  heat pumps run in the cheap hours, so fewer air heat pumps (183 vs. 196)
  deliver more heat.
- The flat smart run is the v4 reference for the heat technologies on the
  new Phase 1 data.

`ev_battery` energy (483 MWh flat, 565 MWh day-ahead) is battery
discharge to driving: under the hourly price more charging goes through
the battery ahead of the trip instead of straight to the car's demand. It
is not cycling, but the lossless battery can still report simultaneous
charge and discharge (see "Open").

## Open

- Survey-based EV parameters for Loenen (occupancy `ev_config`).
- **Battery throughput reporting.** Add a tiny battery loss, or a
  `cost_flow_out` on the battery, to remove the degenerate simultaneous
  charge/discharge if battery throughput is to be reported.
