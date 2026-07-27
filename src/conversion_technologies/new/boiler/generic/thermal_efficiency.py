"""Shared boiler thermal-efficiency helpers.

Boilers are simple single-carrier-in/single-carrier-out conversion
technologies, so unlike heat pumps (temperature-dependent COP) there is no
curve to compute here -- just the handful of derating rules every boiler
type shares.
"""

from __future__ import annotations


def derated_efficiency(
    nominal_efficiency: float, part_load_factor: float = 1.0
) -> float:
    """Apply a simple part-load derating to a boiler's nameplate efficiency.

    Parameters
    ----------
    nominal_efficiency : float
        Manufacturer nameplate efficiency at full load, in (0, 1].
    part_load_factor : float
        Fraction of full load the boiler is assumed to run at on average, in (0, 1].
        The default (1.0) returns the nameplate efficiency unchanged.

    Returns
    -------
    float
        The derated efficiency, capped at 1.0.
    """
    if not 0.0 < nominal_efficiency <= 1.0:
        raise ValueError("nominal_efficiency must be in (0, 1].")
    if not 0.0 < part_load_factor <= 1.0:
        raise ValueError("part_load_factor must be in (0, 1].")
    # Condensing boilers recover more latent heat at lower firing rates; a small
    # empirical bonus below full load, capped so efficiency never exceeds 1.0.
    bonus = (1.0 - part_load_factor) * 0.03
    return min(nominal_efficiency + bonus, 1.0)
