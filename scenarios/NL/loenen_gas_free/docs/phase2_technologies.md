# Phase 2 — non-gas technology export

**Status: done.**

## Checks performed

| Check | Result |
| --- | --- |
| `conversion_technologies` importable from a plain interpreter | **No**, initially — not installed anywhere on this machine (no dedicated `conversion_env` conda env exists either, same gap as `buem_env` in Phase 1). Base `python` resolves to the Microsoft Store alias stub (not a real interpreter); the real interpreter is `AppData\Local\Python\bin\python.exe`, Python 3.14.3 — compatible with this repo's `requires-python = ">=3.12"`. |
| Fix | Created a scratch venv (`.venv_scenario_check/`, gitignored — not the project's real environment, just enough to run checks) and `pip install -e .` into it. This pulls `weather[pointquery] @ git+...@main` per `pyproject.toml`, so it needs network access; running in background. |
| Gas technology ids identified for exclusion, against the real `technologies.csv` | `boiler,gas,{household,building,community}` and `combined_heat_and_power,gas,{household,building,community}` — confirmed by reading `src/conversion_technologies/new/technologies.csv` directly, not assumed. |
| Non-gas technology ids this scenario will request | `boiler_electric_{household,building,community}`, `boiler_biomass_{household,building,community}`, `heat_pump_electric_{household,building,community}`, `heat_pump_geothermal_{household,building,community}`, `combined_heat_and_power_biomass_{household,building,community}` — pending confirmation of exact registered id spelling via `list_technology_ids()` once the venv install finishes. |

## Completed steps and results

1. `pip install -e .` into `.venv_scenario_check/` finished clean.
2. Real registered ids pulled via `list_technology_ids()` — **CHP's real
   prefix is `chp_`, not `combined_heat_and_power_` as first guessed** from
   the category folder name; corrected before writing the config. Full
   list: `boiler_{biomass,electric,gas}_{household,building,community}`,
   `chp_{biomass,gas}_{household,building,community}`,
   `heat_pump_{electric,geothermal}_{household,building,community}` (21
   ids total; 15 non-gas).
3. `scenarios/NL/loenen_gas_free/technologies/export_config.json` written with
   exactly the 15 non-gas ids (`boiler_electric_*`, `boiler_biomass_*`,
   `heat_pump_electric_*`, `heat_pump_geothermal_*`, `chp_biomass_*`, all
   three scales each) — `boiler_gas_*`/`chp_gas_*` not included.
4. Ran `conversion-technologies export-all --config
   scenarios/NL/loenen_gas_free/technologies/export_config.json -o
   scenarios/NL/loenen_gas_free/technologies/export/loenen_gas_free_techs.yaml`.
   Result: **"Wrote ... (15 technologies)"** plus
   `loenen_gas_free_techs.additional_math.yaml` (expected — both heat pump
   variants are multi-carrier). `grep -r natural_gas
   scenarios/NL/loenen_gas_free/technologies/export/` returns **zero
   matches** — confirmed, not assumed, that constraint #1 in
   `constraints.md` holds in the actual generated YAML. Spot-checked
   `boiler_biomass_building`'s body against `docs/calliope_schema_mapping.md`'s
   documented shape — matches (`carrier_in: biomass`, `flow_out_eff: 0.87`,
   wrapped `cost_*` fields).

## Next

This phase's output (`technologies/export/loenen_gas_free_techs.yaml` +
`.additional_math.yaml`) is the fixed technology catalog every building
node in Phase 3 will choose from. Nothing here is per-building yet —
that's Phase 3's job once Phase 1's demand data exists.
