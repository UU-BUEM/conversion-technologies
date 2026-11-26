# Phase 7: the electricity grid (workflow step 1)

**Status (2026-11-25): built for Loenen from Liander's open data, and
from pylovo.** All 1,260 buildings are assigned to an MV/LV station and,
for Liander, an LV feeder. The pylovo run and its cross-check against
Liander are in "pylovo run for Loenen" below. Design context:
`energy_community_workflow.md`, step 1.

## What it produces

`scripts/build_grid.py` writes a **grid package** to
`data/grid/<source>/` (git-ignored, see "Licence" below). The format is
the same whatever the source:

| File | Content |
| --- | --- |
| `transformers.csv` | one row per MV/LV station: `trafo_id`, `name`, WGS84 position, `rated_kva`, `n_transformers`, `peak_kw`, `nbl_limit_kw`, `peak_date`, `data` (`rated` or `geometry_only`), `source_id` |
| `building_grid_map.csv` | one row per building: `building_feature_id`, `bag_pand_id`, position, `trafo_id`, `feeder_id`, `network_distance_m` (cable route from the station), `connection_distance_m` (centroid to nearest cable), `method` |
| `lv_lines.geojson` | LV cables (WGS84) with `trafo_id`, `feeder_id`, `cable_type` (null for Liander) |
| `manifest.json` | source, inputs, licence, every assumption, counts, diagnostics |
| `cross_check.csv` | only with `--cross-check`: each station's nearest DSO station |

`method` is one of:

- `lv_network`: traced along the cables
- `provided`: given by the user
- `pylovo`
- `euclidean`: no cables available at all
- `euclidean_fallback`: the cables did not reach a station

## Three sources, in order

```bash
# scenario root, scenario_env
python scripts/build_grid.py                      # --source auto
python scripts/build_grid.py --source provided --provided-dir data/grid_provided
python scripts/build_grid.py --source dso         # Liander
python scripts/build_grid.py --source pylovo --pylovo-url http://localhost:8086 --cross-check
```

`auto` uses the first source available:

1. **`provided`.** Used when `--provided-dir` (default
   `data/grid_provided/`) contains a `transformers.csv`. Optional files,
   best first:
   - `building_grid_map.csv`: the real assignment, used as given;
   - `lv_cables.geojson`: traced like the DSO tier;
   - with neither, the nearest station in a straight line.

   A full pandapower network (`net.json`) is not read yet; see
   "Environment".
2. **`dso`.** Liander's open data. Used when Liander has MV rooms in the
   area. Other DSOs (Enexis, Stedin) publish similar data, but only the
   Liander adapter exists so far.
3. **`pylovo`.** Used when a pylovo API answers on `--pylovo-url`. The
   client sends a buffered convex hull of the buildings to
   `POST /generate-grid` and maps each BAG building to the OSM footprint
   that contains its centroid, which gives its `grid_result_id`.
   `--cross-check` compares the synthetic stations with Liander's.

## Liander data used

| Dataset | Content | Licence |
| --- | --- | --- |
| *Liggingsgegevens elektriciteitsnetten*: ArcGIS FeatureServer `Liander_Open_Data_Elektra` (EPSG:28992) | layer 642 MV stations (`FUNCTIE_HOOFDGROEP` = `Ruimte`), 112 LV cables, plus 643 LV cabinets, 424 MV cables, 641 HV station. **Geometry only**: no cable types, ratings or connectivity | CC BY 4.0 |
| *Netbewust publiek laden, dataset knelpunt 2026-01* (CSV) | one row per MV/LV transformer: MSR number, WGS84 position, rated capacity, peak load, Netbewust Laden limit, peak date | **may not be shared with third parties without Liander's written permission**; data quality "indicative" |

Endpoints are in `scripts/grid/liander.py`. The service URL was resolved
from ArcGIS item `11b7bcf1b78b4462b91db0dff234cf78`. Responses are cached
in `data/grid_cache/`.

## Method (DSO and provided-with-cables tiers)

1. **Stations.** Liander's transformers are grouped per MSR (station) and
   moved onto the nearest Liander MV room within 75 m. All 105 matched
   rooms were within 4.4 m. Rooms with no row in the transformer list are
   kept as `geometry_only` stations.
2. **Cable graph.** A cable's end joins any vertex of another cable within
   1 m. Interior vertices of two cables are never joined, so cables that
   only cross stay separate.
3. **Attachment.**
   - A station connects to every cable end within 30 m.
   - A building connects to the nearest cable within 75 m of its centroid.
     Service cables are not in the data.
4. **Assignment.** Each building goes to the station with the shortest
   cable route (multi-source shortest path). Real LV networks are radial,
   with normally-open points that the data does not show; this split
   stands in for them.
5. **Feeder.** The first cable leaving the station on that route.

All parameters are CLI flags and are recorded in `manifest.json`.

## Results for Loenen (2026-11-25)

The input is buem's summary
(`data/loenen_single_dwelling_summary_cool26_ev20.parquet`), area = the
buildings' extent plus 1 km.

| | |
| --- | --- |
| Liander assets in the area | 149 MV rooms, 1 HV station, 47 LV cabinets, 4,055 LV and 1,652 MV cable pieces |
| Rated transformers in the list | count and ratings in `data/grid/dso_liander/LICENSED_FIGURES.md` (local only, licensed) |
| Stations serving the 1,260 buildings | 42 (some without a published rating; median 10.5 buildings, max 179), 103 feeders |
| Assigned along the cables | 1,229 buildings; 31 fall back to a straight line (21 with no cable within 75 m) |
| Cable route, station → building | median 219 m, P90 450 m, max 964 m |
| Connection distance, building → cable | median 14 m, P90 26 m |
| Same station as a plain nearest-station rule | 76% (so tracing matters) |
| Busiest station | 179 single dwellings (rating and published peak: local note) |

**Decision: unrated MV rooms may feed buildings**
(`--unrated-stations include`, the default).

- **With `exclude`:** only stations in the transformer list may feed
  buildings. 91 buildings then get cable routes over 1 km (maximum 2.4 km),
  and every one of them sits next to an unrated room.
- **With `include`:** every route stays under 1 km, and straight-line
  fallbacks drop from 68 to 31.

So the transformer list is incomplete for some stations that do feed the
LV network. The cost is that **some buildings sit on stations with no
published rating** (counts in the local note). Step 3 needs a rating for these. The options are a data
request to Liander (Partners in Energie), a sourced typical rating, or
pylovo's sizing; this is not decided yet.

## pylovo run for Loenen (2026-11-25)

**Setup.** A clone of `enerplanet/enerplanet-pylovo` at `6586b69`, in
`D:/test/enerplanet-pylovo`, with all LFS data pulled. Local additions,
none committed upstream:

- `docker-compose.loenen.yml`: an override that runs Postgres, Redis and
  one API instance on port 8086, without HAProxy. Postgres is sized for a
  31 GB Docker VM instead of the 64 GB server upstream targets.
- `.env.docker`: local default credentials, no EP-Online key.

No `make` is available on Windows, so the Makefile recipes were run by hand.

```bash
cd D:/test/enerplanet-pylovo
docker network create spatialhub-net
docker compose -f docker-compose.yml -f docker-compose.loenen.yml up -d postgres redis
gunzip -c raw_data/pylovo_db_full.sql.gz | docker exec -i pylovo-postgres psql -U postgres -d pylovo_db -v ON_ERROR_STOP=1 -q
docker compose -f docker-compose.yml -f docker-compose.loenen.yml up -d --build pylovo-api-1
export MSYS_NO_PATHCONV=1   # Git Bash would rewrite /app/... into a Windows path
# OSM clipped to the buildings' extent + ~2 km
docker exec pylovo-api-1 bash -c "cd /app/raw_data/loenen && osmium extract -b 5.918,52.059,6.103,52.169 gelderland-latest.osm.pbf -o loenen_clip.osm.pbf"
docker exec pylovo-api-1 python -m datapipeline.main --country netherlands --state gelderland --pbf /app/raw_data/loenen/loenen_clip.osm.pbf
docker exec pylovo-api-1 python -m datapipeline.prepare_country netherlands
#   (then the state_code workaround below)
docker exec pylovo-api-1 python runme/main_constructor.py --datapipeline --country netherlands --state gelderland
docker exec pylovo-api-1 python runme/create/generate_grid.py netherlands gelderland --worker 16
cd D:/test/conversion-technologies/scenarios/NL/loenen_gas_free
python scripts/build_grid.py --source pylovo --cross-check      # scenario_env
```

Clipping the OSM data turns the whole-province job into one of a few
minutes. Grid generation covers only postcodes with buildings and roads
loaded: 18 postcodes, 245 s, including Loenen's 7371 with 44 LV grids.

**Upstream problems met** (worth reporting to enerplanet-pylovo):

1. **Province codes.** `prepare_country netherlands` leaves the province
   code empty for 4,070 of 4,080 postcodes. The current CBS PC4 workbook
   has no province column, and the script says so itself. The constructor
   then refuses the import. Workaround: set `state_code = gelderland` for
   the 20 postcodes that intersect the study box, which lies entirely in
   Gelderland. The original file is kept as `postcode_netherlands.csv.orig`.
2. **3D BAG enrichment fails.** The tile index
   `https://data.3dbag.nl/v20240420/tile_index.fgb` returns 403, and the
   fallback query sends an EPSG:3035 bbox to `api.3dbag.nl`, which returns
   400.
3. **CBS enrichment fails.** The OData download returns an empty body.
4. **EP-Online is skipped** without an API key. The pipeline continues
   without energy labels.

Because of 2–4, pylovo sized loads **without building heights, household
counts or energy labels**, from footprints only. OSM also maps no
distribution transformers in the area (one substation only), so every
MV/LV station is pylovo's own greenfield placement.

**Result** (`data/grid/pylovo/`):

- 1,246 buildings matched to pylovo's OSM footprints; 14 straight-line
  fallbacks.
- 36 stations serve them: 13 × 160, 6 × 250, 6 × 400 and 11 × 630 kVA.
- No feeder ids: pylovo's API returns none.

**Cross-check against Liander**, counting only stations that serve the
1,260 buildings:

| | Liander (real) | pylovo (synthetic) |
| --- | --- | --- |
| Stations | 42 | 36 |
| Capacity | licensed (local note) | 12,910 kVA |
| Distance to nearest station of the other grid | median 234 m, P90 655 m | median 222 m, P90 469 m |
| Buildings per station | median 10.5, max 179 | median 16, max 257 |

Agreement on which buildings share a station:

- adjusted Rand index 0.57;
- 70% of building pairs that share a Liander station also share a pylovo
  station, and 53% the other way round.

**Reading:**

- pylovo gets the *number* of stations about right.
- It places them roughly 200 m from the real ones; only 11% of all its
  stations are within 50 m of a Liander station.
- It very likely oversizes them: Liander's total rating, even with a
  typical rating assumed for its unrated stations, stays well below
  pylovo's 12.9 MVA (figures in the local note).

So for Loenen the DSO grid stays the reference. The pylovo grid is the
fallback for areas without DSO data, and its station loading should be
read with that oversizing in mind.

## Licence: keep it local

The knelpunt CSV and anything containing its numbers (`transformers.csv`
`rated_kva`/`peak_kw`/`nbl_limit_kw`, and `manifest.json`) stay in
`data/`, which is git-ignored. Do not commit them, publish them, or send
them to EnerPlanET or anyone else without Liander's written permission.
The cable and station geometry is CC BY 4.0 and may be shared with
attribution.

## Environment

`scenario_env` gained `shapely`, `pyproj`, `networkx`, `scipy` and
`pytest` (pip, 2026-11-25; Calliope 0.7.0 still imports).

`pandapower` was **not** added: pip would downgrade pandas from 3.1 to
2.3, and numpy with it, inside the Calliope environment. Power flow (step 3)
therefore gets its own environment. That is also when a provided
pandapower `net.json` becomes readable.

## Tests

```bash
python -m pytest scenarios/NL/loenen_gas_free/tests -q   # scenario_env, repo root
```

The tests cover:

- tracing on a synthetic network: route choice, a joined branch, an
  unjoined crossing, fallbacks, feeders;
- package validation;
- grouping and matching of Liander transformers;
- all three provided modes;
- conversion of a pylovo response;
- the cross-check.

They need no network access and no Liander data.

## Open

- **Ratings for the unrated stations** (counts in the local note), before step 3.
- **pylovo enrichment.**
  - An EP-Online API key (free, <https://apikey.ep-online.nl/>) would add
    energy labels.
  - 3D BAG and CBS need upstream fixes (see "Upstream problems met").
  - Rerun the pylovo tier after either, then check whether its sizing moves
    closer to Liander's.
- **LV cable types.** Liander gives none. Step 3 needs an assumption, a
  data request, or pylovo's types.
- **Missing buildings.** The 75 multi-unit buildings and all
  non-residential buildings are not in the building list, so station
  loading from these 1,260 houses is a lower bound. Liander's peak values
  include everyone.
