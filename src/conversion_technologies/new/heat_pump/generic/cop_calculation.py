"""Shared coefficient-of-performance (COP) formulas for heat pump technologies.

Both air-source and ground-source heat pumps derive their nominal COP the
same way -- a Carnot (thermodynamic-limit) COP scaled down by a "quality"
(second-law) efficiency factor that captures real-compressor losses. Only
the design source/sink temperatures and the quality factor differ per
technology, so that data lives in each technology's ``data/defaults.json``.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray


def carnot_cop(
    t_source_c: float | ArrayLike, t_sink_c: float, carnot_efficiency: float
) -> float | NDArray[np.float64]:
    """Heating COP at one or more source temperatures.

    ``t_source_c`` may be a single design-point temperature (COP at a fixed
    design condition) or an array-like of temperatures -- e.g. an hourly
    ``T`` series from the ``weather`` package's ``get_point_weather()``
    (2 m air temperature, deg C: the harmonised output of COSMO-REA6's raw
    ``T_2M``, ERA5-Land's ``t2m`` and MERRA-2's ``T2M``), the real consumer
    in ``new/heat_pump/weather_cop.py``. The same formula applies elementwise
    either way.

    Parameters
    ----------
    t_source_c : float or array-like
        Heat source temperature(s), degrees Celsius (outdoor air, ground loop, ...).
    t_sink_c : float
        Heat sink (delivery) temperature, degrees Celsius (e.g. radiator flow temp).
    carnot_efficiency : float
        Second-law/quality efficiency in (0, 1] capturing real-compressor
        losses relative to the theoretical Carnot limit.

    Returns
    -------
    float or numpy.ndarray
        COP = heat delivered / electricity consumed. Scalar input raises if
        the sink/source gap is non-positive; array input returns NaN at any
        timestep where it is (e.g. source already warmer than the sink).
    """
    if not 0.0 < carnot_efficiency <= 1.0:
        raise ValueError("carnot_efficiency must be in (0, 1].")
    t_sink_k = t_sink_c + 273.15

    if np.isscalar(t_source_c):
        t_source_k = float(t_source_c) + 273.15  # type: ignore[arg-type]
        delta = t_sink_k - t_source_k
        if delta <= 0:
            raise ValueError("t_sink_c must exceed t_source_c for a heating COP.")
        return carnot_efficiency * t_sink_k / delta

    t_source_k_arr = np.asarray(t_source_c, dtype=np.float64) + 273.15
    delta_arr = t_sink_k - t_source_k_arr
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(delta_arr > 0, carnot_efficiency * t_sink_k / delta_arr, np.nan)
