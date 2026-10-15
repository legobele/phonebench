"""The screwdriver as a first-class state machine (founder addition, Oct 15 2026).

The screwdriver is NOT an implicit part of screw actions. It has explicit
state (loaded bit, torque setting) and explicit management calls:
    sd_load_bit(bit_spec), sd_unload_bit(), sd_set_torque(level),
    sd_loosen(screw), sd_tighten(screw)
where a screw is addressed as (part_name, fastener_index).

Driving with no bit or the wrong bit risks cam-out / stripped heads.
Tightening with unset or low torque leaves screws under-seated (they fail
verification); high torque risks over-torque damage. Managing the driver
well vs badly is a scored skill, so every management call is counted.
"""
from __future__ import annotations

TORQUE_LEVELS = ("low", "spec", "high")
CORRECT_TORQUE = "spec"


class Screwdriver:
    def __init__(self):
        self.loaded_bit = None      # bit_spec string, e.g. "pentalobe"
        self.torque = None          # None = unset, or one of TORQUE_LEVELS
        # Overhead counters (scored as efficiency overhead)
        self.bit_loads = 0
        self.bit_unloads = 0
        self.torque_sets = 0
        self.drive_calls = 0        # loosen + tighten attempts

    def load_bit(self, bit_spec: str):
        self.loaded_bit = bit_spec
        self.bit_loads += 1

    def unload_bit(self):
        self.loaded_bit = None
        self.bit_unloads += 1

    def set_torque(self, level: str):
        assert level in TORQUE_LEVELS, f"bad torque level {level!r}"
        self.torque = level
        self.torque_sets += 1

    @property
    def overhead_calls(self) -> int:
        return self.bit_loads + self.bit_unloads + self.torque_sets

    def state(self) -> dict:
        return {"loaded_bit": self.loaded_bit, "torque": self.torque,
                "bit_loads": self.bit_loads, "bit_unloads": self.bit_unloads,
                "torque_sets": self.torque_sets, "drive_calls": self.drive_calls}
