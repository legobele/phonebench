"""Opening-tool parameter state (founder ruling, 2026-10-15).

Tool behaviour is NOT a fixed sim constant: the agent sets the
parameters, because choosing the number is part of the skill being
benchmarked. This module holds the two parameter state machines of the
opening family, built exactly like the screwdriver's (sim/screwdriver.py):
explicit state, explicit setter calls, every setter counted as overhead.

- HeatPlate: the heating element's temperature in degrees C. `None`
  means UNSET, and unset reproduces the sim's legacy default behaviour
  (soften_adhesive simply works), so pre-ruling runs, tests, and
  policies stay valid. Once set, soften_adhesive resolves by band:
      temp <  SOFTEN_MIN_C            adhesive does not soften
      SOFTEN_MIN_C..SOFTEN_MAX_C      softens cleanly
      SOFTEN_MAX_C..RISK_MAX_C        softens, thermal-damage roll
                                      (a battery: certain thermal event)
      temp >  RISK_MAX_C              softens, certain thermal damage
- OpeningClamp: an AntiClamp-style bench clamp. It holds the phone
  while suction pulls the panel with a metered, even force — no prying.
  Its pressure is an agent-set force level on the shared F0-F4 scale;
  UNSET pressure resolves to the legacy working default (F2) at open
  time, exactly as an omitted call argument does.

Both live on the Bench, so — like screwdriver bit/torque state — the
settings persist across a Marathon queue unless explicitly managed.
Settings are visible through observe() and metrics().
"""
from __future__ import annotations

FORCE_LEVELS = ("F0", "F1", "F2", "F3", "F4")
FORCE_RANK = {level: i for i, level in enumerate(FORCE_LEVELS)}
DEFAULT_FORCE = "F2"          # the legacy working force when nothing is set


class HeatPlate:
    MIN_C = 20.0              # element's plausible range: settings outside
    MAX_C = 150.0             # it are refused at set time
    SOFTEN_MIN_C = 60.0       # below this the adhesive never softens
    SOFTEN_MAX_C = 100.0      # top of the clean softening band
    RISK_MAX_C = 120.0        # above SOFTEN_MAX_C: damage roll; above
                              # RISK_MAX_C: certain thermal damage

    def __init__(self):
        self.temp_c = None    # None = unset -> legacy default behaviour
        self.temp_sets = 0

    def set_temp(self, temp_c: float):
        self.temp_c = temp_c
        self.temp_sets += 1

    def state(self) -> dict:
        return {"temp_c": self.temp_c, "temp_sets": self.temp_sets}


class OpeningClamp:
    def __init__(self):
        self.pressure = None        # F-level or None (unset -> F2 at open)
        self.engaged_part = None    # part the clamp currently holds
        self.pressure_sets = 0
        self.engage_calls = 0
        self.release_calls = 0
        self.open_calls = 0         # op_clamp_open attempts (work calls)

    def set_pressure(self, force: str):
        assert force in FORCE_LEVELS, f"bad force level {force!r}"
        self.pressure = force
        self.pressure_sets += 1

    def engage(self, part: str):
        self.engaged_part = part
        self.engage_calls += 1

    def release(self):
        self.engaged_part = None
        self.release_calls += 1

    @property
    def overhead_calls(self) -> int:
        """Management calls (the scored overhead): pressure sets,
        engages, and releases — the analogue of screwdriver overhead."""
        return self.pressure_sets + self.engage_calls + self.release_calls

    def state(self) -> dict:
        return {"pressure": self.pressure, "engaged_part": self.engaged_part,
                "pressure_sets": self.pressure_sets,
                "engage_calls": self.engage_calls,
                "release_calls": self.release_calls,
                "open_calls": self.open_calls,
                "overhead_calls": self.overhead_calls}
