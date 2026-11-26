# Generation technologies

`conversion_technologies.generation_technologies` holds technologies that
generate a carrier instead of converting one: Calliope `supply`
technologies whose available output per hour depends on weather and site.
Today it has rooftop photovoltaics (`pv`).

It is a separate subpackage from `new` (conversion: carrier in -> carrier
out) with its own `technologies.csv` and `costs.csv`, read by the same
loader. Every value is traced in `docs/sources/parameter_sources.csv`.

## Ownership

| Module | Owns |
| --- | --- |
| buem | Building geometry only: the roof faces (tilt, azimuth, area) in its region summary (`roof_faces`), and the facts `has_pv` / `pv_capacity_kwp`. buem is a demand model and computes no PV output. |
| weather | The weather variables (`T`, `DHI`, `DNI`, `WS_10M`), curated per provider. |
| this subpackage | Which roof faces carry PV and how much, the hourly PV profile, and PV as a Calliope technology (costs, lifetime). |
| scenario | Which buildings may get PV, export/feed-in rules, solving. |

## Consistency with EnerPlanET

- **Profile model.** EnerPlanET's PV service,
  [enerplanet/pysam-pv](https://github.com/enerplanet/pysam-pv), runs NREL
  PVWatts v8 through NREL-PySAM. `pv/pvwatts.py` uses the same PySAM
  module and version (7.1.1), the same weather variables, the same
  timestamp handling (UTC, any minute of the hour, leap day run
  separately), the same filling of missing values and the same defaults
  (losses 0.14, DC/AC ratio 1.1, inverter efficiency 0.96, standard
  module, roof mount). `tests/test_pv.py` runs a pinned copy of the
  service's own `simulate.py` (`tests/data/pysam_pv/`) and this engine on
  the service's MERRA-2 2018 test weather and requires identical hourly
  output (to 1e-12 kW), for four array set-ups, missing values and a leap
  year. The service rounds its capacity factors to 4 decimals; this
  package keeps full precision.
- **Weather.** From UU-BUEM [`weather`](https://github.com/UU-BUEM/weather) (the module EnerPlanET
  uses): `get_point_weather(..., wind=True)` (weather >= 1.11) gives
  `T`, `DHI`, `DNI` and the 10 m wind speed `WS_10M`. PVWatts uses the
  wind speed only for the module temperature (it returns NaN without
  it); nothing here models wind power. Nothing here downloads or
  derives weather. With an
  older weather package, `fetch_weather` raises and asks for a weather
  DataFrame instead.
- **Costs.** From [THD-Spatial-AI/OpenTech-DB](https://github.com/THD-Spatial-AI/OpenTech-DB)
  (`solar_pv_distributed`): household = `solar_pv_dist_res_6kw_de`
  (residential 6 kW, German standard 2024), building =
  `solar_pv_dist_small_comm_30kw`, converted USD2024 -> EUR2025 as for the
  other USD sources. These are US/German prices and probably above Dutch
  rooftop prices; a sourced Dutch value can replace them in `costs.csv`.

## The technology

`pv_rooftop_household`, `pv_rooftop_building`:

```yaml
base_tech: supply
carrier_out: electricity
source_unit: per_cap      # source_use_max = AC output per kWp in each hour
flow_out_eff: 1.0         # losses are already inside the profile
flow_cap_max: ...         # kWp (DC); catalogue ceiling, the roof bounds it per node
cost_flow_cap: ...        # EUR2025 per kWp
cost_om_annual: ...       # EUR2025 per kWp and year
lifetime: 25
```

`flow_cap` is the DC nameplate (kWp). The profile is AC output per kWp,
so the inverter clipping at DC/AC 1.1 is inside it too.

**The scenario must always supply `source_use_max` where the technology is
placed**: without it Calliope treats the source as unlimited.
`write_pv_profiles` writes the profile and the node placement together
for that reason.

## Roof faces -> arrays

`pv/roof.py`, rules in `technologies.csv` (assumptions, see the sources
file):

| Rule | Value |
| --- | --- |
| Faces smaller than `min_face_area_m2` carry no PV | 10 m2 |
| Faces flatter than `flat_roof_max_tilt` get a rack at `flat_roof_tilt`, facing `flat_roof_azimuth` | 10 deg; 15 deg, south |
| Pitched faces more than `max_azimuth_from_south_deg` from south carry no PV | 90 deg (east to west via south) |
| Potential per face | area x `roof_usable_fraction` (0.6) x `kwp_per_m2` (0.2) |

A building's profile is the capacity-weighted mean of its faces' profiles,
and its `flow_cap_max` the sum of their potentials. The optimiser sizes
one PV capacity per building, spread over its faces in proportion; it
does not fill the best face first.

## Use

```bash
conversion-technologies pv-profile pv_rooftop_household \
    --roof-faces roof_faces.json --latitude 52.2 --longitude 6.0 \
    --year 2018 --provider merra-2 -o nodes/pv
```

`roof_faces.json` is `{node: [{"id", "tilt", "azimuth", "area_m2"}]}`,
e.g. built from buem's `roof_faces` summary column. Output:
`pv_rooftop_household_source_use_max.csv` (rows timesteps, columns
nodes), `..._data_tables.yaml` and `..._nodes.yaml` (placement with
`flow_cap_max` per node). Python API: `pv.pvwatts.pv_capacity_factors`,
`pv.roof.roof_pv`, `pv.roof.building_capacity_factor`,
`pv.profiles.write_pv_profiles`.

NREL-PySAM is an optional dependency (`pip install
conversion-technologies[pv]`; conda: `nrel::nrel-pysam=7.1.1.post1`).

## Limits

- No shading, snow or soiling beyond the lumped 14% loss (as PVWatts and
  pysam-pv).
- One capacity per building, spread over its faces in proportion.
- With `CONVERSION_TECH_PARAMS_DIR` (custom parameter folder) set, both
  `new` and this subpackage read their `technologies.csv`/`costs.csv`
  from that one folder, so it must contain the `pv` rows (with all
  columns of this subpackage's tables) or PV is not registered.
- MERRA-2 irradiance runs high in central Europe (pysam-pv: about
  1,300 kWh/kWp for a south-facing 35 deg array in Deggendorf on 2018
  weather); the yield follows the weather provider chosen.
