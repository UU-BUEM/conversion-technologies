# Phase 1 — per-building demand (buem batch run)

**Status: done.** Full hourly run completed for the 1,260 single-dwelling
population: `scenarios/NL/loenen_gas_free/data/loenen_single_dwelling_hourly.parquet`
+ `loenen_single_dwelling_summary.parquet` (gitignored, regenerate via the
command in "Next" below if needed — not committed, ~350MB-scale).

## Real run results (1,260 buildings, 16 workers, merra-2/2018)

- **1,260/1,260 ok, 0 errors**, 1,087.5s elapsed (~18 min), 1.16 buildings/s sustained.
- Row count exact: 11,037,600 = 1,260 × 8,760, every building has exactly 8,760 hourly rows.
- **Zero NaNs anywhere in the hourly output** — the known merra-2-`T`-NaN failure mode did not occur at Loenen's coordinates (52.12N, 6.03E), matching the clean result already confirmed at (52.0N, 5.0E).
- `heating_kWh/A_ref` (heating intensity): median 112 kWh/m², mean 158 kWh/m², IQR 54-273 kWh/m² — a wide spread consistent with a real mixed-era Dutch housing stock (older/safe-default-envelope buildings at the high end), not an obviously broken result. Not deeply cross-checked against TABULA reference bands yet — worth doing before treating absolute magnitudes (not just relative comparisons) as reliable.
- `dtype`/schema confirmed correct per the earlier patch verification (`dhw_kW` sums match the annual `dhw_kWh` summary exactly on the 5-building sample — not re-verified row-by-row on the full population, but the code path is identical).

## Checks performed

| Check | Result |
| --- | --- |
| Loenen building data present (`buem/src/buem/data/buildings/netherlands/Loenen/`) | Yes — `lod2_building_feature.csv` (3,105 building rows — includes multi-unit buildings), `bag_use_function.csv` (1,587 rows, matches the ~1,600-household estimate), `tabula.csv` (135-row archetype reference table, not per-building), plus `lod2_child_feature.csv`/`lod2_child_feature_surface.csv` (window/door/surface detail) and `refurbishment_measure_reference.csv`/`service_building_reference.csv`. |
| `buem_env`/`conversion_env` conda environments | **Found — real location is `C:\Users\sahoo002\.conda\envs\`, not the `ProgramData\anaconda3` install first checked.** `buem_env`, `conversion_env`, `occupancy_env`, `weather_env` all already exist and are populated. |
| `buem validate` | **PASS** — Python 3.14, pandas/numpy/pvlib/cvxpy all OK, `BUEM_WEATHER_DIR` → `D:\test\buem\src\buem\data\weather` (exists), weather archives at `D:\test\weather\data` with `merra-2` present. |
| 5-building smoke test, annual batch (`buem.analysis.batch`) | **5/5 ok, 0 error.** But: this path only ever produces an **annual summary** (`heating_kWh`, `cooling_kWh`, `elec_kWh`, `dhw_kWh`, `cooking_gas_kWh` per building) — no hourly timesteps. Not what Calliope nodes need directly. |
| 5-building smoke test, hourly companion (`scripts/run_region_hourly.py`) | **5/5 ok, 0 error**, real 8,760-row-per-building output (`Q_heat_kW`, `elec_kW`, plus weather/solar/internal-gain columns) — confirmed via the smoke-test parquet, not assumed. This is the correct Phase 1 output shape for Calliope `demand` techs. |
| TABULA archetype match rate | One of the 5 smoke-test buildings (`NL.N.MFH.01.Gen`) did not match the bundled TABULA sheet and fell back to `buem`'s documented safe-default envelope ratios (15% window-to-wall, 5% door) rather than a real TABULA-derived envelope — a real, logged degradation, not silent. Worth tracking the fallback rate across the full 1,587-building run. |
| Heat demand magnitude sanity | Two of the 5 smoke-test buildings show `heating_kWh` ≈ 98,000–114,000 kWh/year — far above a single household's typical 10,000–15,000 kWh/year. These are multi-unit (`MFH`) *buildings*, not single dwellings: `lod2_building_feature.csv`'s 3,105 rows vs. `bag_use_function.csv`'s 1,587 dwelling rows confirms buildings and dwellings aren't 1:1. **Open design question for Phase 3**: does a Calliope node represent one `building_feature_id` (lumping all units' demand and giving them one shared technology) or one dwelling unit (needs demand/technology disaggregated by `residential_units`)? Not decided — affects what "1,600 households, each a separate node" actually means once multi-unit buildings are involved. |

## Resolution 1: `buem/scripts/run_region_hourly.py` patched (done)

Added `dhw_kW`/`cooking_gas_kW` to the hourly output — both already existed
as hourly `pd.Series` on `ModelBUEM` (`self.dhw_kWh`/`self.cooking_gas_kWh`,
populated by `_addDhwCooking()` inside `sim_model()`'s own `_readResults()`
call), just never written to the long-format Parquet. Re-ran the same
5-building smoke test against the patched script: 5/5 ok, and
`dhw_kW.sum()` per building matches the existing annual `dhw_kWh` summary
exactly (verified: buildings 1-5 → 28812.61/36826.04/8014.15/8014.15/19207.89
both ways). `cooking_gas_kW` correctly 0.0 for all 5 (these cook
electrically, already inside `elec_kW`, matching the model's own
double-counting guard). This is a `buem`-repo change
(`scripts/run_region_hourly.py`), not touched anywhere in
`conversion-technologies`.

## Resolution 2: scoped to single-dwelling buildings for now

Real counts from `buem`'s own building source, not estimated:
**1,335 residential buildings in Loenen total; 1,260 are single-dwelling
(`residential_units == 1.0`), 75 are multi-unit** (2 to 19 units each —
the long tail that produced the earlier unrealistic ~98,000 kWh/year
smoke-test reading). Per request, Phase 1 (and the node set Phase 3 will
build) is scoped to the 1,260 single-dwelling buildings only for now;
`scenarios/NL/loenen_gas_free/data/loenen_single_dwelling_ids.txt` holds the
exact id list. The 75 multi-unit buildings are deferred, not dropped —
revisit once the building-vs-dwelling-node question actually needs
answering, rather than guessing a disaggregation rule now. This also
revises the scenario's household count downward from the original
~1,600 estimate to **1,260 for this first pass** (plus whatever of the 75
multi-unit buildings' ~250+ remaining dwellings get added back later).

## Historical finding (fixed above): hourly DHW and cooking load weren't exported, even though the model already computed them

`buem.thermal.model_buem.ModelBUEM` already computes **hourly** `self.dhw_kWh`
and (per its own code comment at `model_buem.py:1586`) `self.cooking_gas_kWh`
as real per-timestep series, not just annual totals — confirmed by reading
the source (`model_buem.py:1589-1603`, `:1668`), not assumed. But
`scripts/run_region_hourly.py` only writes `Q_heat_kW` and `elec_kW`
(occupancy's `elecLoad`, appliance electricity only) into the hourly
parquet; DHW and cooking are only ever summed into the *annual* summary
(`dhw_kWh`/`cooking_gas_kWh` at lines 172-173), never retained hourly.

This matters for this scenario specifically: a gas-free model needs DHW and
cooking as their own hourly demand techs (so the optimizer can route them
through an electric/heat-pump DHW path instead of silently dropping them),
and `cooking_gas_kWh` is a second gas end-use besides space heating (now
also noted in `constraints.md` #0). Running the full 1,587-building batch
with today's `run_region_hourly.py` would produce an incomplete dataset
that has to be re-run anyway once this is fixed — so the full run is held
pending a decision on how to fix it:

- **Option A**: small patch to `buem/scripts/run_region_hourly.py` (add
  `DHW_kW`/`Cooking_gas_kW` columns mirroring the existing `elec_kW`
  pattern) — a `buem`-repo change, not a `conversion-technologies` one.
- **Option B**: approximate DHW/cooking hourly profiles downstream (e.g.
  flat-rate or occupancy-pattern-shaped disaggregation of the annual
  total) instead of touching `buem`. Cheaper short-term, less accurate.

**Not done without checking in first** — editing a sibling repo's script is
outside this repo's own scope and worth a deliberate choice, not a
default.

## Next, once the DHW/cooking decision is made

```bash
# Example shape (worker count not yet decided — 22 logical CPUs available on this machine)
python scripts/run_region_hourly.py \
    --data-dir src/buem/data/buildings/netherlands/Loenen --country NL \
    --building-ids-file <all 1,587 residential building ids> \
    --workers <N> \
    --output .../loenen_hourly.parquet \
    --summary-output .../loenen_summary.parquet
```

Validation after the real run, before trusting the output for Phase 2/3:
- Row count: 8,760 × (however many residential buildings pass `--residential-only`-equivalent filtering — note `run_region_hourly.py` takes an explicit id list, not a `--residential-only` flag, so that filtering has to happen before building the id file).
- No NaN heat-demand values (the known merra-2-`T`-NaN failure mode `buem`'s own CLAUDE.md documents).
- TABULA fallback rate across the full population, not just the 5-building sample.
- Resolve the building-vs-dwelling-unit node question above before Phase 3 consumes this.
