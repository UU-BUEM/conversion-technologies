# pysam-pv reference copy

Verbatim files from [enerplanet/pysam-pv](https://github.com/enerplanet/pysam-pv),
EnerPlanET's PV service, at the commit in `COMMIT`:

- `simulate.py` (from `pv_service/simulate.py`): the PVWatts v8 run the
  service uses.
- `merra2_2018_deggendorf.json` (from `tests/data/`): a year of MERRA-2
  weather at Deggendorf in the weather service's JSON shape.
- `LICENSE`: MIT, Copyright (c) 2026 BigGeoData & Spatial AI, Technische
  Hochschule Deggendorf.

`tests/test_pv.py` runs this `simulate.py` and
`conversion_technologies.generation_technologies.pv.pvwatts` on the same
weather and requires identical hourly output, so this package's PV profiles
stay consistent with EnerPlanET's. Do not edit these files; to follow a
new pysam-pv release, replace them and update `COMMIT`.
