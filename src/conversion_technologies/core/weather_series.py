"""Generic hourly time-series CSV reading: validated, then aligned to a year.

Reads the CSV contract the sibling ``weather`` package's
``weather.export.export_single_point_csv()`` already produces: a timestamp
column (first column) plus one or more named value columns, one row per
hour, UTC. This module has no dependency on the ``weather`` package itself
-- only on that documented file shape -- so this package doesn't inherit
``weather``'s much heavier geospatial dependency stack (netCDF4, xarray,
cfgrib, dask, pyproj, scipy) for what is, from here, just a CSV with a
temperature column. See ``docs/calliope_schema_mapping.md`` "Weather-driven
COP profiles" for the integration this exists to support.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def read_hourly_series(path: str | Path, *, column: str) -> pd.Series:
    """Read ``column`` from the weather CSV at ``path`` as an hourly series.

    The first CSV column is the timestamp index. Normalises a tz-aware index
    to naive UTC wall-clock (so it lines up with :func:`align_to_year`'s
    tz-naive expected index regardless of whether the source CSV wrote an
    explicit UTC offset). Raises ``ValueError`` -- not a bare pandas
    exception -- if the file is missing, ``column`` isn't present, the index
    isn't parseable as timestamps, there are duplicate timestamps, or
    consecutive timestamps aren't uniformly 1 hour apart.
    """
    csv_path = Path(path)
    if not csv_path.is_file():
        raise ValueError(f"Weather CSV not found: {csv_path}")

    try:
        frame = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    except Exception as exc:  # pandas raises several exception types here
        raise ValueError(
            f"'{csv_path}': could not read as a CSV with a timestamp index: {exc}"
        ) from exc

    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError(
            f"'{csv_path}': first column could not be parsed as timestamps."
        )
    if column not in frame.columns:
        raise ValueError(
            f"'{csv_path}': column '{column}' not found. Available columns: "
            f"{list(frame.columns)}."
        )

    index = frame.index
    if index.tz is not None:
        index = index.tz_convert("UTC").tz_localize(None)

    series = pd.Series(frame[column].to_numpy(dtype=float), index=index, name=column)
    series = series.sort_index()

    if series.index.has_duplicates:
        dupes = series.index[series.index.duplicated()]
        raise ValueError(
            f"'{csv_path}': duplicate timestamps, e.g. {dupes[0]!r} "
            f"({len(dupes)} total)."
        )
    if len(series) < 2:
        raise ValueError(f"'{csv_path}': need at least 2 rows to check hourly spacing.")

    deltas = series.index.to_series().diff().dropna()
    irregular = deltas[deltas != pd.Timedelta(hours=1)]
    if not irregular.empty:
        gap_end = irregular.index[0]
        gap_start = series.index[series.index.get_loc(gap_end) - 1]
        raise ValueError(
            f"'{csv_path}': timestamps are not uniformly 1 hour apart -- gap "
            f"of {irregular.iloc[0]} between {gap_start} and {gap_end} "
            f"({len(irregular)} irregular gap(s) total)."
        )

    return series


def align_to_year(
    series: pd.Series, year: int, *, max_missing_fraction: float = 0.0
) -> pd.Series:
    """Reindex ``series`` onto every expected hourly timestamp for ``year``.

    8760 or 8784 rows depending on whether ``year`` is a leap year -- always
    computed from ``year``, never assumed, since ``weather``'s own docs note
    leap-day truncation in some of its "representative year" products.
    Raises ``ValueError`` if the fraction of expected timestamps with no
    matching input row exceeds ``max_missing_fraction`` (default 0: require
    complete coverage), naming the count and the first missing timestamp.
    """
    if not 0.0 <= max_missing_fraction <= 1.0:
        raise ValueError(
            f"max_missing_fraction must be in [0, 1], got {max_missing_fraction}."
        )

    expected_index = pd.date_range(
        start=f"{year}-01-01 00:00:00", end=f"{year}-12-31 23:00:00", freq="h"
    )
    aligned = series.reindex(expected_index)
    missing = aligned.isna()
    missing_count = int(missing.sum())
    missing_fraction = missing_count / len(expected_index)
    if missing_fraction > max_missing_fraction:
        first_missing = expected_index[missing][0]
        raise ValueError(
            f"Weather series covers only {(1 - missing_fraction):.1%} of {year} "
            f"at hourly resolution (missing {missing_count} of "
            f"{len(expected_index)} hours, e.g. {first_missing}); "
            f"max_missing_fraction={max_missing_fraction} not satisfied."
        )
    return aligned
