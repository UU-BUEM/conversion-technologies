# Phase 8 (workflow step 2): demand and supply per building and station

Status 2026-11-25: built and run for Loenen, final for this weather year.
All Phase 1 runs here use buem with TABULA-based window sizing, window
shading and summer window ventilation (`--window-ach 3`); see "Cooling:
fixed in buem". The first round (flat 50% glazing, no ventilation) is kept
as `data/*.before_windows.parquet`.
Workflow context: `energy_community_workflow.md`, step 2.

## What step 2 produces

One table set per scenario, for every building that loads the grid, summed
per Liander station from step 1. Nothing is optimised here; step 3 (power
flow, headroom) and step 5 (community filter) read these tables.

| Output (`data/step2/`, git-ignored) | Content |
| --- | --- |
| `building_annual.csv` | one row per building and scenario: role, type, era, envelope variant, annual heat/hot water/cooling/appliance/EV energy, peaks, PV potential, station and feeder |
| `<scenario>/station_hourly.parquet` | per station and hour: summed `elec_kW`, `ev_kW`, `electric_kW` (= elec + ev), `heat_kW`, `dhw_kW`, `cool_kW`, and `pv_potential_kW` (every usable roof at its maximum) |
| `station_summary.csv` | per station and scenario: annual energy, coincident peaks, building counts, PV potential, Liander rating and measured peak |
| `region_summary.csv` | one row per scenario |
| `manifest.json` | every input path (the full per-building hourly data stays in the Phase 1 parquets) |
| `pv/` | PV inputs and outputs (`pv_building_potential.csv`, per-kWp profiles, `thomassen_pv.csv`/`.json`) |
| `grid/dso_liander/` | the step 1 grid package rebuilt for all 1,398 buildings |

## Buildings

| Role | Count | Demand source |
| --- | --- | --- |
| `single_dwelling` | 1,260 | the scenario's own Phase 1 run (these are the buildings with Calliope models) |
| `background` | 138 | one baseline run, added unchanged to every scenario |

The background set is every residential building outside the 1,260-list
(75; buem's unit counts changed after Phase 1, so only 28 of them are now
recorded as multi-unit) plus the 63 buildings with a service type
(warehouse 22, supermarket 15, restaurant 14, office 9, school 2, clinic 1).
The other 1,585 non-residential 3D BAG objects have no service type and a
median footprint of 31 m2 (sheds, garages); they are left out.

All 1,398 map to the same 42 Liander stations as in step 1 (1,354 traced
along cables, 44 straight-line fallback). None of the 1,260 changed station.

## Scenarios

| Scenario | Single dwellings | Phase 1 run |
| --- | --- | --- |
| `baseline` | buem envelope (TABULA variant from the energy label), EV ownership 20% | `loenen_single_dwelling_{hourly,summary}_cool26_ev20.parquet` |
| `retrofit_standard` | every dwelling at least TABULA variant 2 | `loenen_single_dwelling_retrofit_v2_cool26_ev20_*.parquet` |
| `retrofit_advanced` | every dwelling at TABULA variant 3 (nZEB level) | `..._retrofit_v3_...` |
| `ev50` | baseline envelope, EV ownership 50% | `loenen_single_dwelling_cool26_ev50_*.parquet` |

**Retrofit** (`scripts/build_retrofit_region.py`): a copy of buem's Loenen
region folder with each residential building's TABULA row lifted to at
least the target variant (never lowered); buem's repository is not edited.
TABULA NL has no standard (002) package for the newest era (06, built 2015 or later), so
those 110 buildings keep their envelope in `retrofit_standard`. Standard
lifts 775 of the 1,260 single dwellings; advanced lifts all of them. The
manifest of each copy is `data/buem_regions/retrofit_v*/retrofit_manifest.json`.

Appliance and EV profiles are identical across the retrofit runs (same
seeds); the EV draw at 50% gives 1.51 GWh/yr of home charging vs 0.71.

## PV supply

`scripts/build_pv_potential.py` runs the package's `conversion-technologies
pv-profile` CLI (subprocess in `conversion_env`, no import) with MERRA-2
2018 weather at the region point (52.12 N, 6.03 E, the same cell as buem).
The processed weather lives in `D:/test/weather/data/merra2/output`
(`--data-dir`); this settles the open question in `HANDOFF_NEXT.md`.

| | Value |
| --- | --- |
| Buildings that can carry PV | 1,244 of 1,260 single dwellings; 20.2 MWp for all 1,398 (incl. a 2.4 MWp warehouse roof) |
| Annual potential | 11.4 GWh (single dwellings), 23.6 GWh (all) vs 11.2 GWh present-day electricity |
| Specific yield | median 1,180 kWh/kWp |

The yield is high for the Netherlands (about 950-1,000 kWh/kWp in sunny
2018). MERRA-2 is known to overestimate irradiance here; treat the PV
energy as an upper estimate, about 15-20% high.

**Thomassen rooftop** (`community_assets.csv`). The site publishes about
800 MWh/yr, but neither its kWp nor which hall carries the panels: the PDOK
address point (Kanaal Zuid 496) falls on a 59 m2 office, with five large
halls 100-300 m away. So the array is one flat roof under the package's
`pv_rooftop_building` flat-roof rule, at the address, scaled so 2018 gives
800 MWh: **675 kWp**, i.e. 281 Wp per panel for 2,404 panels, plausible for
2020 modules. The calibration absorbs the MERRA-2 bias; the layout only
shapes the profile. The nearest Liander LV station is far too small to
carry 675 kWp: the site must have its own MV
customer connection (not in Liander's open data). Step 3 has to attach it
to the MV network, not to an LV station.

## Results (2018 weather)

Region, 1,398 buildings:

| Scenario | Electricity GWh | Electric peak MW | Heat GWh | Heat peak MW | Cooling GWh |
| --- | --- | --- | --- | --- | --- |
| baseline | 11.17 | 2.58 | 60.0 | 28.4 | 5.5 |
| retrofit_standard | 11.17 | 2.58 | 37.2 | 19.6 | 5.6 |
| retrofit_advanced | 11.17 | 2.58 | 32.3 | 17.5 | 5.7 |
| ev50 | 11.97 | 2.76 | 60.0 | 28.4 | 5.5 |

Heat excludes hot water (5.7 GWh in every scenario). Median per single
dwelling: heat 18.1 MWh (standard retrofit 8.1, advanced 4.5), cooling
1.8 MWh. Cooling is the ideal load to hold 26 degC; its coincident peak
(17.7 MW on the hottest afternoon) is a demand bound, not installed
equipment, because few Dutch homes have cooling at all.

Electricity is present-day load (appliances, lighting and uncontrolled
home EV charging); heat, hot water and cooling are thermal and still need a
heating technology to become electricity (step 3's electrified variant).
The region peak falls on a November weekday at 17:30; station peaks are
17:00-19:00 in winter.

**Validation against Liander.** For the stations with a published rating
and measured peak, the modelled present-day electric peak agrees closely
with Liander's measured peaks; a few stations exceed their rating already
in the model. Figures in `data/grid/dso_liander/LICENSED_FIGURES.md` (local only, licensed). This is the first independent
check of buem/occupancy electricity at station level, and it holds.
Caveats: Liander's peak (2025) also carries existing heat pumps, EVs and
the unmodelled small objects; the model has the 2018 weather and an EV
draw.

**PV vs grid.** At most rated stations the rooftop PV potential exceeds
the station rating (figures in the local note). Full rooftop
PV is not hostable without curtailment, storage or reinforcement, which is
the question step 3 quantifies per feeder.

## Cooling: fixed in buem

The first round gave implausible cooling at 26 degC (baseline 23 GWh,
about 10 MWh per dwelling) that *rose* with retrofit (775 upgraded homes:
heat 39.7 -> 9.0 MWh/yr, cooling 8.4 -> 20.5 MWh/yr). Three buem changes
(2026-11-25, buem CHANGELOG):

1. **Window areas** (the root cause). Every exposed LOD2 wall was 50%
   glass: TABULA NL's mean window / *net* wall ratio across all types,
   applied to *gross* walls. Detached houses got 2-2.5x TABULA's glazing
   (building 1186: 105 m2 of windows on 110 m2 of wall); median window
   solar gain 27 MWh/yr per dwelling, correlated 0.72 with cooling. Now each
   building uses its own TABULA archetype's glazing share of the gross
   facade, which varies by type and era and not by refurbishment variant:

   | Type | era 01 (to 1964) | 02 (1965-74) | 03 (1975-91) | 04 (1992-2005) | 05 (2006-14) | 06 (2015+) |
   | --- | --- | --- | --- | --- | --- | --- |
   | SFH (detached) | 0.17 | 0.23 | 0.22 | 0.21 | 0.18 | 0.18 |
   | TH (terraced) | 0.30 | 0.39 | 0.32 | 0.30 | 0.39 | 0.39 |
   | MFH | 0.26 | 0.35 | 0.26 | 0.28 | 0.51 | 0.51 |
   | AB (apartment block) | 0.30 | 0.45 | 0.23 | 0.34 | 0.38 | 0.38 |

   Windows now come to 16-20% of floor area in the checked homes.
2. **Window shading.** Window gains now carry buem's external shading
   factor (`F_sh_vert` 0.75 facade, `F_sh_hor` 0.8 roof), as the opaque
   gains already did.
3. **Summer window ventilation** (`n_air_window_max`, opt-in, here 3 extra
   air changes per hour, an assumption for tilted or open windows). The LP
   may remove heat `Q = H_w (T_air - T_e)` with `0 <= H_w <= H_window` where
   it saves cooling, offered only in hours where ventilation can only cool:
   outdoor air at or below the heating setpoint, or at least 1 K below the
   indoor temperature of a window-free first pass (a second solve). Heating
   never changes.

Six test homes, cooling kWh/yr (sum):

| | Before | Windows + shading | + ventilation 3/h |
| --- | --- | --- | --- |
| baseline | 72,409 | 14,081 | 10,014 |
| standard retrofit | 117,757 | 16,395 | 9,199 |

Region result: cooling 23.2 -> 5.5 GWh, median per dwelling 10.3 -> 1.8
MWh; retrofit now changes cooling by +3 to +5% instead of +37 to +49%.
Heating fell 2.6% in the region (6% in the test homes: less glass, less
loss). buem's CBS validation pages were run with the old windows and
should be rerun.

## Commands

From the scenario root unless noted. Phase 1 runs: `buem_env`, repo root,
about 15 min each with 16 workers with `--window-ach 3` (two LP passes).

```bash
python scripts/build_retrofit_region.py --target-variant 2 --out data/buem_regions/retrofit_v2
python scripts/build_retrofit_region.py --target-variant 3 --out data/buem_regions/retrofit_v3
bash data/run_step2_phase1.sh   # baseline + background + retrofit_v2 + retrofit_v3 + ev50, --window-ach 3
python scripts/build_grid.py --source dso --out-root data/step2/grid \
    --buildings data/loenen_single_dwelling_summary_cool26_ev20.parquet \
                data/loenen_background_cool26_ev20_summary.parquet
python scripts/build_pv_potential.py \
    --summary data/loenen_single_dwelling_summary_cool26_ev20.parquet \
    --summary data/loenen_background_cool26_ev20_summary.parquet   # ~10 min
python scripts/build_step2_profiles.py
```

Phase 1 wrapper options added here: `--region-dir` (a retrofit copy),
`--ids-file` (e.g. `data/loenen_background_ids.txt`), `--window-ach`.

**scenario_env gotcha:** NumPy's matrix product crashes Python on Windows
(`0xc06d007f`, exit 127, no traceback) unless the environment's
`Library/bin` is on PATH: `export PATH="$E/Library/bin:$E:$PATH"` (same as
for CBC).

Tests: `python -m pytest scenarios/NL/loenen_gas_free/tests` (retrofit
rule, PV nodes parsing).

## Open items

- The per-building Calliope results (`outputs/v4`) were solved on the old
  demand; re-solve when they are next needed.
- Window ventilation rate (3/h) is an assumption; a sensitivity run (1.5, 5)
  would bound it.
- Electrified variant (heat pumps for heat, hot water and cooling) in step
  3, using the package's weather-driven COP.
- Thomassen MV connection point; the five candidate halls.
- MERRA-2 PV bias: compare with another provider (ERA5-Land) or PVGIS.
- Multi-unit buildings still have no Calliope model (lumped load only).
