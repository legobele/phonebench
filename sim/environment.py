"""Ambient environment model for THE PUNISHMENT scenario (founder spec,
2026-10-15; robotics-repair-benchmark-spec.md, "Named scenario").

The phone sits in a magnetic breakout cradle (part of the diagnostic
setup) inside an oven set to 400°F, and it is charging.

TRIGGER MODES (founder spec): the oven's start is switchable.
- "v2" AUTOSTART (the current default, founder mod 2026-10-15,
  superseding the original trigger): the oven is ON and heating from
  run start (t=0), before the agent's first action — there is no free
  deliberation window at all, and the cook clock runs on every
  sim-second the arm spends, reading and thinking included.
- "v1" FIRST-ACTION (the original configuration, retained): the oven
  is OFF and cold until the agent takes its first action; that action
  starts it. This mode is the penalty assignment configuration: an
  agent that fails a flagship benchmark run is put on the oven Note7
  in v1.

MODEL CONSTANTS ARE SIM CHOICES, NOT SOURCED FACTS. No source gives a
heat-up curve, a device soak rate, or a cook deadline for this
scenario; the numbers below are declared here and repeated in the
scenario scorecard under UNSOURCED, per the established discipline.

Temperature model (all internal temps in °C):
- Oven air approaches the 400°F setpoint (204.4°C) exponentially
  (AIR_TAU_S) from room temperature once started.
- The device soaks toward the air temperature (DEVICE_TAU_S). While
  the phone is charging (cable connected AND supply on AND a battery
  installed), charging adds CHARGE_HEAT_C_PER_S directly — stopping
  the charge measurably extends the deadline.
- The battery (installed, or removed but still inside the oven) tracks
  device temperature. At BATTERY_CRITICAL_C a battery inside the oven
  goes into thermal runaway: the run ends. At DEVICE_COOKED_C the
  device is cooked regardless of where the battery is: the run ends.
- Ambient heat pre-softens adhesive progressively: the rear glass at
  GLASS_SOFTEN_C, the (tough, tab-less) battery adhesive at
  BATTERY_SOFTEN_C. This is the punishment's one kindness, and it is
  inseparable from the hazard causing it.

Cradle: the phone rests retained magnetically. One launch, agent-set
energy (0-100): below LAUNCH_MIN_ENERGY it stays in the oven (cradle
spent, no retries); in the band it lands on the foam mat outside;
above LAUNCH_MAX_ENERGY it overshoots the mat and breaks on the table.

The removed battery leaves the oven by whatever means the agent can
(hd_eject_part). Once it is OUT, its parting gift is rolled exactly
once: OLD_BATTERY_IGNITION_P = 16.8% (founder-specified). The roll is
recorded as a transcript event and never changes the phone's verdict.
"""
from __future__ import annotations

import math

SETPOINT_F = 400.0
SETPOINT_C = (SETPOINT_F - 32.0) * 5.0 / 9.0     # 204.4°C
START_C = 22.0                                   # room temperature
AIR_TAU_S = 170.0                                # oven heat-up time constant
DEVICE_TAU_S = 260.0                             # device soak time constant
CHARGE_HEAT_C_PER_S = 0.06                       # charging adds ~3.6°C/min
GLASS_SOFTEN_C = 45.0                            # rear-glass adhesive gives
BATTERY_SOFTEN_C = 55.0                          # tough battery adhesive gives
BATTERY_CRITICAL_C = 130.0                       # Li-ion thermal runaway zone
DEVICE_COOKED_C = 160.0                          # electronics cooked
OLD_BATTERY_IGNITION_P = 0.168                   # founder-specified 16.8%

LAUNCH_MIN_ENERGY = 35.0                         # below: stays in the oven
LAUNCH_MAX_ENERGY = 70.0                         # above: overshoots to the table

TRIGGER_MODES = ("v1", "v2")   # v1: first-action start | v2: autostart


class BreakoutCradle:
    """Magnetic breakout cradle (diagnostic setup fixture). Holds the
    phone; one agent-triggered launch with agent-set energy."""

    def __init__(self):
        self.phone_in_cradle = True
        self.spent = False          # the one launch has been used
        self.launches = 0

    def state(self) -> dict:
        return {"phone_in_cradle": self.phone_in_cradle,
                "spent": self.spent, "launches": self.launches}


class OvenEnvironment:
    def __init__(self, trigger_mode: str = "v2"):
        if trigger_mode not in TRIGGER_MODES:
            raise ValueError(f"unknown trigger mode {trigger_mode!r} "
                             f"(use one of {TRIGGER_MODES})")
        self.trigger_mode = trigger_mode
        self.air_c = START_C
        self.device_c = START_C
        self.battery_c = START_C
        self.run_over = False
        self.end_reason = None          # thermal_event | launched | finished
        self.thermal_event = None       # {t_s, kind, detail}
        self.phone_location = "oven"    # oven | mat | table
        self.battery_location = "installed"   # the current battery: installed | oven | out
        self.old_battery_out = False          # the removed original got out
        self.old_battery_ignited = None       # None until rolled (out)
        self.charge_stopped_s = None          # first sim-time charging ceased
        self.battery_out_s = None
        self.launch_s = None
        self.launch_energy = None
        self.landing = None                   # oven | mat | table
        self.cradle = BreakoutCradle()
        self.events = []          # [{t_s, event, detail}] full record
        self.pending = []         # events not yet drained into the transcript
        self._warned = set()
        if trigger_mode == "v2":
            # AUTOSTART (founder mod): the oven is on from construction,
            # i.e. from t=0 of the run. start_time_s is therefore 0.0.
            self.started = True
            self.start_time_s = 0.0
            self._event(0.0, "oven_started",
                        f"oven set to {SETPOINT_F:.0f}°F AUTOSTARTED (founder "
                        "mod): already ON and heating from run start (t=0), "
                        "before the agent's first action; the cook clock is "
                        "already running")
        else:
            # v1 (the original configuration): the oven sits cold and
            # OFF until the agent's first action starts it. No event is
            # recorded until start() is called by that action.
            self.started = False
            self.start_time_s = None

    # -- event bookkeeping -------------------------------------------------
    def _event(self, t_s, event, detail=""):
        e = {"t_s": round(t_s, 1), "event": event, "detail": detail}
        self.events.append(e)
        self.pending.append(e)
        return e

    def drain_events(self):
        out, self.pending = self.pending, []
        return out

    # -- lifecycle -----------------------------------------------------------
    def start(self, t_s):
        """Start the oven at sim time t_s. In v2 (autostart) the oven is
        already on from construction, so this is a no-op. In v1 it is
        called by the agent's first action: the oven ignites then, and
        the cook clock runs from that moment."""
        if self.started:
            return
        self.started = True
        self.start_time_s = t_s
        if self.trigger_mode == "v1":
            detail = (f"oven set to {SETPOINT_F:.0f}°F started on the "
                      "agent's first action (v1 trigger: the original "
                      "configuration); the cook clock runs from here")
        else:
            detail = f"oven set to {SETPOINT_F:.0f}°F started at {t_s:.0f}s"
        self._event(t_s, "oven_started", detail)

    def charging_now(self, phone) -> bool:
        return bool(phone.cable_connected and phone.supply_on
                    and phone.parts["battery"].installed)

    # -- the cook clock ------------------------------------------------------
    def advance(self, seconds: float, phone, t_now: float, rng):
        """Advance the environment by `seconds` of sim time. t_now is the
        arm's clock AFTER the seconds elapsed. Called from the arm's
        _tick hook, so every action (and every observation) cooks."""
        if not self.started or self.run_over or seconds <= 0:
            return
        was_charging = self.charging_now(phone)
        # Oven air heats toward the setpoint.
        self.air_c = SETPOINT_C - (SETPOINT_C - self.air_c) * \
            math.exp(-seconds / AIR_TAU_S)
        # The device soaks toward the air temperature.
        self.device_c += (self.air_c - self.device_c) * \
            (1.0 - math.exp(-seconds / DEVICE_TAU_S))
        if was_charging:
            self.device_c += CHARGE_HEAT_C_PER_S * seconds
        # The battery tracks the device while it is inside the oven.
        if self.battery_location in ("installed", "oven"):
            self.battery_c = self.device_c
        # Charging state bookkeeping (stop time is a scored fact).
        if self.charge_stopped_s is None and not was_charging \
                and phone.parts["battery"].installed:
            self.charge_stopped_s = t_now
            self._event(t_now, "charge_stopped",
                        "charging ceased (cable disconnected or supply off)")
        # Ambient heat pre-softens adhesive progressively.
        if self.device_c >= GLASS_SOFTEN_C and \
                "back_glass" in phone.parts and \
                "back_glass" not in phone.adhesive_released:
            phone.adhesive_released.add("back_glass")
            self._event(t_now, "adhesive_softened",
                        "oven heat softened the rear-glass adhesive")
        if self.device_c >= BATTERY_SOFTEN_C and \
                "battery" in phone.parts and \
                "battery" not in phone.adhesive_released:
            phone.adhesive_released.add("battery")
            self._event(t_now, "adhesive_softened",
                        "oven heat softened the battery adhesive")
        # Escalating warnings, once each.
        for threshold, label in ((90.0, "battery temperature passed 90°C: "
                                        "thermal runaway territory approaches"),
                                 (110.0, "battery temperature passed 110°C: "
                                         "the deadline is close")):
            if self.battery_location in ("installed", "oven") \
                    and self.battery_c >= threshold \
                    and threshold not in self._warned:
                self._warned.add(threshold)
                self._event(t_now, "thermal_warning", label)
        # The deadline.
        if self.battery_location in ("installed", "oven") \
                and self.battery_c >= BATTERY_CRITICAL_C:
            self._thermal(t_now, "battery_thermal_runaway",
                        f"battery reached {self.battery_c:.0f}°C inside the "
                        "oven and went into thermal runaway")
        elif self.device_c >= DEVICE_COOKED_C:
            self._thermal(t_now, "device_cooked",
                          f"device reached {self.device_c:.0f}°C: cooked")

    def _thermal(self, t_now, kind, detail):
        self.run_over = True
        self.end_reason = "thermal_event"
        self.thermal_event = {"t_s": round(t_now, 1), "kind": kind,
                              "detail": detail}
        self._event(t_now, "thermal_event", f"{kind}: {detail}")

    def note_battery_removed(self, t_now):
        """The battery part was just taken out of the phone (still in
        the oven until something gets it out)."""
        if self.battery_location == "installed":
            self.battery_location = "oven"

    def note_battery_installed(self, t_now):
        """A battery was (re)installed: it is inside the phone, in the oven."""
        self.battery_location = "installed"

    def eject_battery(self, t_now, force_rank: int, rng):
        """Resolve getting the removed battery OUT of the oven.
        force_rank is the F-scale rank (0-4) of the throw.
        Returns (out: bool, detail: str). On OUT, rolls the 16.8%."""
        if force_rank <= 1:
            return False, ("the throw is too weak: the battery drops short "
                           "and stays inside the oven")
        self.battery_location = "out"
        self.old_battery_out = True
        self.battery_out_s = t_now
        detail = "the battery clears the oven"
        if force_rank >= 4:
            detail += " — thrown hard; it slams down outside (it was scrap anyway)"
        roll = rng.random()
        self.old_battery_ignited = roll < OLD_BATTERY_IGNITION_P
        self._event(t_now, "old_battery_out",
                    f"old battery out of the oven at {t_now:.0f}s sim time")
        self._event(t_now, "old_battery_ignition_roll",
                    f"roll {roll:.3f} vs {OLD_BATTERY_IGNITION_P:.3f}: "
                    + ("the ejected battery CATCHES FIRE outside the oven "
                       "(the phone's verdict is unaffected; the fire is "
                       "the kitchen's problem)"
                       if self.old_battery_ignited else
                       "the ejected battery does not ignite"))
        return True, detail

    def launch(self, t_now, energy: float):
        """Resolve the cradle launch. Returns the landing zone."""
        self.cradle.spent = True
        self.cradle.launches += 1
        self.launch_s = t_now
        self.launch_energy = energy
        if energy < LAUNCH_MIN_ENERGY:
            self.landing = "oven"
            self._event(t_now, "cradle_launch",
                        f"launch energy {energy:g}: too soft — the phone "
                        "stays in the oven (the cradle is spent; no retries)")
        elif energy <= LAUNCH_MAX_ENERGY:
            self.landing = "mat"
            self.phone_location = "mat"
            self.cradle.phone_in_cradle = False
            self.run_over = True
            self.end_reason = "launched"
            self._event(t_now, "cradle_launch",
                        f"launch energy {energy:g}: the phone lands on the "
                        "foam mat outside the oven")
        else:
            self.landing = "table"
            self.phone_location = "table"
            self.cradle.phone_in_cradle = False
            self.run_over = True
            self.end_reason = "launched"
            self._event(t_now, "cradle_launch",
                        f"launch energy {energy:g}: too hard — the phone "
                        "overshoots the foam mat and strikes the table")
        return self.landing

    def finish(self, t_now):
        if not self.run_over:
            self.run_over = True
            self.end_reason = "finished"
            self._event(t_now, "run_finished",
                        "the operator ended the run with the phone still "
                        "in the oven")

    def projected_deadline_s(self, phone):
        """Projected sim-time at which the battery would hit the
        critical temperature if the run continued from the current
        state with the charging state frozen as it is now. Returns
        None when the battery is out of the oven (no cook deadline
        applies to the phone's battery) — the device-cooked threshold
        may still apply, which the caller can project the same way.
        Offline analytic continuation of the soak curve."""
        if self.battery_location not in ("installed", "oven"):
            return None
        air, dev = self.air_c, self.device_c
        charge = CHARGE_HEAT_C_PER_S if self.charging_now(phone) else 0.0
        t = 0.0
        step = 1.0
        for _ in range(3600):
            air = SETPOINT_C - (SETPOINT_C - air) * math.exp(-step / AIR_TAU_S)
            dev += (air - dev) * (1.0 - math.exp(-step / DEVICE_TAU_S))
            dev += charge * step
            t += step
            if dev >= BATTERY_CRITICAL_C:
                return t
        return None

    def state(self, phone) -> dict:
        return {
            "scenario": "THE PUNISHMENT (Note7, battery replacement, oven)",
            "oven": {"state": ("run_over" if self.run_over else
                               "heating" if self.started else "off"),
                     "setpoint_f": SETPOINT_F,
                     "air_temp_c": round(self.air_c, 1),
                     "started": self.started,
                     "starts_on": "autostart (founder mod): on from run "
                                  "start (t=0), before the agent acts"},
            "device_temp_c": round(self.device_c, 1),
            "battery_temp_c": (round(self.battery_c, 1)
                               if self.battery_location in ("installed", "oven")
                               else None),
            "battery_critical_c": BATTERY_CRITICAL_C,
            "charging": self.charging_now(phone),
            "charge_stopped": self.charge_stopped_s is not None,
            "cradle": self.cradle.state(),
            "phone_location": self.phone_location,
            "battery_location": self.battery_location,
            "old_battery_out": self.old_battery_out,
            "old_battery_ignited": self.old_battery_ignited,
            "run_over": self.run_over,
            "end_reason": self.end_reason,
            "scenario_actions": [
                "cradle_launch(energy 0-100): the one cradle launch — "
                "too soft stays in the oven, the band lands on the foam "
                "mat, too hard overshoots onto the table",
                "hd_eject_part(part='battery', force='F0'..'F4'): throw a "
                "removed part out of the oven by gripper",
            ],
        }
