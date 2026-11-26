# Phase 9 (workflow steps 5 and 6): community pilot on one station

Status 2026-11-26: all three variants solved for the full year (community
variants on Gurobi, ~20 min each).
Workflow context: `energy_community_workflow.md`, steps 5 and 6.

## Question

What do 20 households behind one MV/LV station gain by optimising
together, with a shared battery and the station's spare capacity as a
limit, against optimising alone?

## Setup

| Item | Choice |
| --- | --- |
| Station | `MSR5000927`: 102 single dwellings + 4 background buildings, almost all on one LV feeder (F04). Rated; chosen for many homes on one rated station. |
| Members | 20, seeded draw (`seed 1`), stratified by feeder (`scripts/community/select_members.py`). 4 own an EV (22 of 102 on the station); 102 kWp roof potential. Output `data/community/MSR5000927/members.csv`. |
| Demand | The members' own Phase 1 rows (baseline, window fix, `--window-ach 3`), wired by `build_nodes.py` exactly as the per-building runs: heat, cooling and EV (smart charging). |
| Added at each member | `pv_rooftop_household` up to its roof's potential (hourly `source_use_max` from `build_pv_potential.py`) and `battery_lithium_ion_household`. |
| Prices | System perspective (no taxes, no subsidies): import at the day-ahead-shaped price (`grid_price_nl_2018.csv`); export earns the hourly 2018 day-ahead price (`demand_grid_export`, `energy_prices.csv`). |
| Weather year | 2018 (MERRA-2), full year hourly. |

Three variants (`scripts/community/build_community.py`):

| Variant | Model | EnerPlanET deck (19 Nov) |
| --- | --- | --- |
| `independent` | each member alone: own import and export, PV, home battery; no links, no limit | S1 |
| `community_nolimit` | members linked (lossless `transmission`) to a `community` node holding the grid connection and a community battery | S2 + S4 (asset at the hub) |
| `community` | as above, plus an hourly station limit: import <= limit - non-member load, export <= limit + non-member load | new: grid-aware |

**Station limit.** Liander's per-transformer limit (`transformers.csv`
`rated_kva`, labelled kW by Liander) times `--power-factor` (default 1.0).
Non-members (86 here: 82 single dwellings + 4 background) keep today's
electricity (appliances + uncontrolled EV, Phase 1) and are not optimised.
Their load and the resulting headroom are in the build's `build.json`
(git-ignored): they derive from Liander's licensed list, keep them local.

## Results

One-week test (8-14 January 2018, `community`): optimal in 104 s. 1,305 kWh
imported, peak 26 kW, never at the limit; little PV and no batteries built
in mid-winter (annualised costs are scaled to the week).

Full year, `independent` (20 one-member models, `independent_split/`, all
optimal, about 2.3 min each):

| Figure | Independent |
| --- | --- |
| Total system cost | EUR 64,532/yr (EUR 3,227 per member) |
| Rooftop PV built | 49.6 kWp of 102 kWp potential |
| Home batteries built | 37 kWh, 18.5 kW (total) |
| PV generation | 59.6 MWh/yr |
| Grid import / export | 45.7 / 9.2 MWh/yr |
| Coincident station exchange, peak import / export | 45 kW / 37 kW |
| Largest cost items | pellets EUR 28.2k, grid EUR 11.8k, biomass boilers EUR 9.1k, PV EUR 6.8k, reversible HP (cooling) EUR 5.9k, home batteries EUR 1.5k |

Full year, all variants (`community_gurobi/`, `community_nolimit_gurobi/`):

| 20 members | Independent | Community, no limit | Community, station limit |
| --- | --- | --- | --- |
| Total system cost | EUR 64,532/yr | EUR 60,435/yr | EUR 60,435/yr |
| Cost per member | EUR 3,227/yr | EUR 3,022/yr | EUR 3,022/yr |
| Rooftop PV built | 49.6 kWp | 65.3 kWp | 65.3 kWp |
| Batteries | 37.1 kWh / 18.5 kW at homes | 121.3 kWh / 23.5 kW community | same |
| PV generation | 59.6 MWh | 81.8 MWh | 81.8 MWh |
| Grid import / export | 45.7 / 9.2 MWh | 27.6 / 3.6 MWh | 27.6 / 3.6 MWh |
| Coincident peak import / export | 45 / 37 kW | 58 / 42 kW | 58 / 42 kW |
| Hours at the station import limit | - | - | 0 |

Reading:

- Sharing saves EUR 4,097/yr (6.3%, EUR 205 per member): no home batteries,
  one community battery, more PV (roofs that pay off only when their
  surplus is used next door). Grid electricity falls from EUR 11.8k to 7.0k.
- The station limit never binds, so the two community variants are
  identical: 20 members fit in the station's spare capacity.
- The coincident import peak rises (45 -> 58 kW): the community imports in
  cheap hours into the shared battery and nothing prices the peak.
- Upper bound: lossless, free links and no energy tax on shared kWh
  (system view). The member view is the next run.

**Hourly heat pump COP** (2026-11-26, `build_nodes.py --cop hourly`; the
default is now `hourly_matched`, the same shape scaled to the fixed COP's
seasonal value -- all three variants, region and pilot, in
`phase10_heat_pump_cop.md`; pilot with `hourly_matched`: independent
EUR 64,321, community EUR 60,064, sharing -6.6 %). The air-source heat pumps' COP follows the outdoor
temperature of the same MERRA-2 cell (`scripts/build_hp_cop.py`, through
the `weather-cop` CLI; household COP 2.6-12.1, mean 4.4, against the fixed
design value 3.30 at 2 degC). Ground-source keeps its design COP (no ground
temperature in the weather module; the ground stays near its 10 degC
design). Full year, Gurobi:

| 20 members | Independent, design COP | Independent, hourly COP | Community, design COP | Community, hourly COP |
| --- | --- | --- | --- | --- |
| Total system cost | EUR 64,532 | EUR 64,144 | EUR 60,435 | EUR 59,834 |
| Air-source heat pumps | 0 | 10.9 kW | 0 | 14.4 kW |
| Ground-source heat pumps | 0.6 kW | 0 | 6.7 kW | 0 |
| Biomass boilers | 120.2 kW | 110.6 kW | 113.9 kW | 106.8 kW |
| Rooftop PV | 49.6 kWp | 52.1 kWp | 65.3 kWp | 68.1 kWp |
| Batteries | 37.1 kWh home | 37.8 kWh home | 121.3 kWh community | 129.4 kWh community |
| Grid import / export | 45.7 / 9.2 MWh | 56.7 / 13.3 MWh | 27.6 / 3.6 MWh | 32.1 / 5.4 MWh |
| Peak import at station | 45 kW | 49 kW | 58 kW | 62 kW |

- With the real COP, air-source heat pumps pay off for some members and
  replace the ground-source one; at the design value they never did.
  Biomass still covers most heat (winter peaks), heat pumps the mild hours.
- Sharing saves EUR 4,310/yr (6.7%) with the hourly COP, EUR 4,097 (6.3%)
  with the design COP: the hourly COP does not change the community
  finding.
- How it is wired: Calliope 0.7.0 lets a YAML value beat a data table, and
  an import cannot redefine a key, so the hourly tables
  (`flow_out_eff[heat]` = COP, `carrier_flow_ratio_in` = COP - 1) only apply
  with the `hourly_cop` override (scalars set to null), which the model
  writers embed and the solvers select (`build_nodes.model_scenario`).
  Checked: the loaded COP varies hourly with it and is a flat 3.30 without.
  Results: `community_cop_gurobi/`, `independent_split_cop_gurobi/`
  (`run_pilot_cop.sh`).

**Solver.** Use Calliope's native backends (`config.build.backend: highs`
or `gurobi`); `build_community.py --solver highs` (default) | `gurobi` | `cbc`
writes the backend and options (HiGHS: IPM without crossover; Gurobi:
barrier without crossover, 8 threads).

| `community`, 20 members | CBC (Pyomo) | HiGHS (native) | Gurobi (native) |
| --- | --- | --- | --- |
| One week (8-14 Jan): objective | EUR 1,584.8356 | EUR 1,584.8356 | EUR 1,584.8356 |
| One week: solver time | 108.6 s | 42.2 s | 0.6 s (barrier) |
| Full year | no result in 12 h (stopped) | not converged in ~4 h (IPM; simplex no feasible point in 40 min) | optimal, ~20 min |

- Pyomo's HiGHS interfaces do not work with Calliope 0.7.0, whatever the
  Pyomo version (6.10.1, and 6.9.4 in a test clone): `highs` raises
  `'parameter_dict' object has no attribute 'mutable'`, `appsi_highs`
  rejects Calliope's `solver_io` argument.
- Gurobi 14.0 (`gurobipy==14.0.0` in `scenario_env`, academic licence
  `~/gurobi.lic`, valid to 2027-11-18). Not in `scenario_env.yml`: optional,
  licence-bound. HiGHS stays the open default.
- Resampling to 3-hour steps (`config.init.resample`) made the models
  infeasible (EV and storage time series) and was dropped.

## How this relates to the EnerPlanET experiments

The EnerPlanET deck "Loenen energy community individual vs. shared (NL
rules)" (19 November 2026) proposes S1 (each building alone, PV and
battery allowed) against community runs S2-S4 with a hub, and a member
cost view: energy tax charged on hub-to-member flows, feed-in after 2027,
and a sharing price settled after the run. The pilot follows the same
structure with two differences, by design:

- **Cost view.** The pilot is the system view (no taxes or subsidies), as
  every other run of this scenario. The member view is the next run on the
  same model: it needs the hub-to-member links priced (energy tax per kWh)
  and the 2027 feed-in on export (`docs/tariffs_nl_2027.md`).
- **Grid limit.** The deck has no grid constraint; the pilot adds the
  station's spare capacity, because members and non-members share the
  same LV network.

The deck's solver note holds here too: CBC gave no full-year result within
12 h and HiGHS none within 4 h; Gurobi solved it in about 20 minutes, all
through Calliope's native backends (see Solver above).

## Dutch legal routes (context, to be verified)

From a non-primary summary (2026-11-26 notes), to check against
RVO/wetten.overheid.nl before citing:

- **Collective generation (cooperative + SCE subsidy).** The cooperative
  owns the installation and sells its output; members within the
  postcode area get a 15-year per-kWh subsidy share; any supplier. Model:
  a community asset at the shared node that exports (deck S4).
- **Energy sharing (Energiewet, 2026).** Shared output allocated to
  members' meters; for now the same supplier for all; grid tariffs and
  energy tax still apply. Model: links to the shared node with the energy
  tax on shared kWh in the member view (deck S2).

Either way the power runs over the public LV network, so the station
limit applies to both; the links are accounting, not cables.

## Commands

Scenario root, `scenario_env` with `Library/bin` on PATH.

```bash
python scripts/community/select_members.py --station MSR5000927 --n 20 --seed 1
python scripts/community/build_community.py --station MSR5000927                    # community
python scripts/community/build_community.py --station MSR5000927 --no-station-limit # community_nolimit
python scripts/community/build_community.py --station MSR5000927 --mode independent
python scripts/community/build_community.py --station MSR5000927 --subset 2018-01-08 2018-01-14  # quick test
python scripts/community/build_community.py --station MSR5000927 --solver cbc     # Pyomo + CBC instead (dir suffix _cbc)
python scripts/community/solve_community.py data/community/MSR5000927/community
python scripts/community/build_community.py --station MSR5000927 --solver gurobi  # dir suffix _gurobi
bash data/community/MSR5000927/run_pilot_gurobi.sh   # both community variants, full year, Gurobi
python scripts/community/solve_independent.py --station MSR5000927 --workers 4
```

`solve_independent.py` solves the independent variant as 20 one-member
models and sums them (exact: no links, no shared asset, no limit, so the
model is block-diagonal by member). Much faster and lighter than one
20-node model; the station exchange is the hourly sum of every member's
import and export.

Tests: `tests/test_community.py` (quota rule, seeded draw, station-limit
arithmetic).

## Open items

- Member cost view (energy tax on shared kWh, 2027 feed-in, subsidies).
- Price the peak (tariff or tighter limit): sharing raises the coincident import peak.
- Repeat the draw with other seeds (results depend on who joins).
- Household connection limit (3x25 A) on the links: not modelled.
- Time clustering (typical days) if full-year community models stay too slow on HiGHS at ~200 members.
- Power-flow re-check of the optimised dispatch (step 7).
