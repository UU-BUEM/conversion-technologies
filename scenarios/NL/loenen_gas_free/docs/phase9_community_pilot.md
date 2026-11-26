# Phase 9 (workflow steps 5 and 6): community pilot on one station

Status 2026-11-26: built; one-week test solved; `independent` full year done;
`community` and `community_nolimit` full year running on HiGHS (the CBC run
was stopped after 12 h without a result).
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

Full year, `community` and `community_nolimit`: running on HiGHS
(`data/community/MSR5000927/run_pilot_highs.sh`, started 2026-11-26 08:28).
To be filled in.

**Solver.** Use Calliope's own HiGHS backend (`config.build.backend: highs`,
`solve.solver: highs`). It calls highspy directly, without Pyomo.
`build_community.py` writes this by default (`--solver highs`); `--solver cbc`
selects the Pyomo backend with CBC.

| One-week test (`community`, 8-14 Jan) | CBC (Pyomo backend) | HiGHS (native backend) |
| --- | --- | --- |
| Status | optimal | optimal |
| Objective | EUR 1,584.8356 | EUR 1,584.8356 |
| Grid import | 1,305.39 kWh | 1,305.39 kWh |
| Solve time (as reported) | 108.6 s | 42.2 s |
| Full year | no result after 12 h (stopped) | running |

Pyomo's HiGHS interfaces do not work with Calliope 0.7.0, whatever the
Pyomo version. Tested in `scenario_env` (Pyomo 6.10.1) and in a clone with
Pyomo 6.9.4 (`scenario_highs_env`, 2026-11-26):

- `highs` (`pyomo.contrib.solver`'s persistent interface) raises
  `'parameter_dict' object has no attribute 'mutable'`, because it does not
  handle the kernel parameters Calliope builds.
- `appsi_highs` fails to construct: Calliope always passes `solver_io` and
  that class does not accept it.

So an older Pyomo is not the fix, and `scenario_highs_env` is not needed.
The Pyomo build of the full-year 20-member model takes about 17 GB. The
HiGHS backend takes about 7.6 GB per model while building.

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
12 h. Its HiGHS option works in Calliope 0.7.0 through Calliope's native
backend, not through Pyomo (see Solver above).

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
bash data/community/MSR5000927/run_pilot_highs.sh   # both community variants, full year, in parallel
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
- Repeat the draw with other seeds (results depend on who joins).
- Household connection limit (3x25 A) on the links: not modelled.
- Time clustering (typical days) if full-year community models stay too slow on HiGHS at ~200 members.
- Power-flow re-check of the optimised dispatch (step 7).
