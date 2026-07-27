# Resolved / BY-DESIGN — boiler

- BY-DESIGN: boilers are always single-carrier-in/single-carrier-out —
  no `generic/` ratio-splitting logic needed here (contrast heat_pump's COP
  split and CHP's power-to-heat split). `generic/thermal_efficiency.py` only
  holds a part-load derating helper.
