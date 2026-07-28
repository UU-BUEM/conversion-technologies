# Resolved / BY-DESIGN — combined_heat_and_power

- BY-DESIGN: CHP is specified directly via energy-hub dispatch factors
  `alpha` (electrical efficiency) and `beta` (thermal efficiency), both
  fractions of fuel input -- `P_elec = alpha * P_fuel`, `P_heat = beta *
  P_fuel` (Geidl & Andersson, 2007, "Optimal Power Flow of Multiple Energy
  Carriers"). Superseded the earlier `total_efficiency` +
  `power_to_heat_ratio` derivation (mathematically equivalent, different
  notation) -- `alpha`/`beta` is the standard notation for this kind of
  multi-carrier conversion tech. See `generic/alpha_beta.py`.
- BY-DESIGN: `primary_carrier_out` is electricity (not heat) for both CHP
  technologies, since electricity is conventionally the "primary" product
  costed/associated in a CHP unit's economics. This field turned out to
  matter beyond naming/cost placement: `calliope_export/ratio_math.py`
  (root `.claude/resolved.md` "ratio-math-fix") uses it directly to know
  which output carrier heat gets tied to -- no CHP-specific code needed
  there because this was already set.
