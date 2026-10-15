"""THE FREEZER — scenario environment, arm, and scoring (founder spec,
2026-10-15; robotics-repair-benchmark-spec.md, "Mirror scenario:
THE FREEZER").

The cold twin of THE PUNISHMENT. A Samsung Galaxy Note7 battery
replacement inside a walk-in freezer. THERMAL START (founder): the
freezer air is already at -40°F (-40°C, the crossover point) and
everything — phone, arm, bench, packs — starts at room temperature
(~22°C) and soaks DOWN toward it. There is no grace period; the
freeze clocks run on every sim-second the arm spends, observations
and monitoring reads included.

TRIGGER MODES (founder): v2 = in the cold on battery from t=0;
v1 = room-temperature AC standby, plunging on the first
non-sensor action; v3 = the system starts OFF and turns on at
t=0 while going into the freezer, eating an immediate 1-minute
boot penalty — no actions possible while the hardware already
soaks; no AC phase, no free window; v4 = the run starts with a
NETWORK ISSUE: cold from t=0 on battery exactly like v2, but the
agent's link to the bench is DOWN until a human operator
physically connects an Ethernet cable at t=2 minutes — and THE
CABLE ITSELF IS A FAILURE POINT (founder): the connect can fail
on the clock (declared seeded failure model, below) while
everything keeps soaking and draining; v5 = DEEP COLD: the
standard cold start (v2-style — in the freezer from t=0, on
battery) with both thermal parameters lowered by the founder:
the hardware starts at 15°C instead of room temperature, and
the freezer air sits at -55°F (-48.3°C) instead of -40.

THREE VISIBLE CLOCKS, ONE HIDDEN ONE:

1. The PHONE freezes: its battery tracks device temperature; at
   BATTERY_CRITICAL_C the phone dies and the run ends. Cold inverts
   the oven's kindnesses: adhesive NEVER softens from ambient (and
   heat-softened adhesive RE-HARDENS if the device falls back below
   ADHESIVE_REHARDEN_C while the part is still closed), glass is
   already at its most brittle, and charging a battery at or below
   0°C is classifier-blocked (lithium plating), the same strength as
   the swollen-battery charge block.
2. The ARM freezes: it soaks toward the air segment by segment
   (base, shoulder, elbow, wrist, gripper — each with its own
   temperature reader; the ELBOW governs, declared). Lubricant
   stiffening stages inflate action time costs, then add fine-motor
   slip risk, and at ARM_CRITICAL_C the arm seizes: run over.
3. The MAIN BENCH PACK drains: 8x 18650 at 3.5V nominal per cell,
   2.7V per-cell cutoff (founder-specified), topology declared below
   as 4S2P. It powers the bench, the arm, and the tools, and it is
   FULLY instrumented (per-cell estimates, draw by load, sag as it
   happens, projected time-to-cutoff). At cutoff the bench dies:
   run over. The source starts on battery at a FULL CHARGE
   (founder); AC exists in the model as the alternative source and
   is NOT switchable mid-run (declared sim choice: the source is a
   setup decision; nobody opens the freezer to swap cables).

THE UTILITY PACK (founder correction): a SEPARATE 5x 18650 pack
(declared topology 5S1P) powers the COMPRESSOR (the suction/vacuum
system: suction cup, opening clamp, air blast) and the HEAT PLATE,
collectively — vacuum work and warming the phone share one fuel
tank. It is deliberately UNDER-instrumented (founder): the agent
gets exactly one readout, the voltage currently on the compressor
batteries, plus automatic threshold warnings (founder addition):
proximity warnings at 0.5V / 0.25V / 0.1V above the cutoff rail
(each once, in the established once-per-threshold style) and a sag
warning whenever a load transient dips the voltage into the 0.25V
band. No capacity, no draw figures, no time-to-cutoff: the rest
must be inferred from the voltage's behavior. At its cutoff the
compressor and the heat plate die TOGETHER; the run continues
without them.

THE CONNECTION CELL (founder addition, as restricted, then
re-architected as a TRUE BACKUP — founder failover ruling): a
solid-state cell, 5V rail, limit 2.7V (founder-specified), stands
behind the bench's designated loads: the agent-to-machine link,
ALL bench lighting (floodlight, tools-area, screw-holding-area,
under-plate), the per-part SENSOR layer (every temp reader fitted
on everything), and a dead-indicator LED (lit only when the cell
is dead). During NORMAL operation those loads run on the main
system and the backup carries NOTHING. The switch fires ONLY when
BOTH the main pack and the utility pack are dead — never on a
single failure (declared single-failure behavior: utility-only
death kills compressor + heat plate and the run continues on the
main pack; main-only death ends the run — the arm is main-powered
and the backup does not engage). The switch is not instantaneous
(founder timing ruling): a startup draw and an internet-connect
draw, each bounded at 30s and skewed hard toward fast (declared
truncated exponentials, 4s mean, seeded per run); during the gap
the designated loads are DOWN — the agent sits in a dark, silent,
senseless bench — and the gap drains the cell at a declared boot
draw. After the connect completes, the ENDGAME begins: the cell
alone carries link + lights + sensors + LED; the arm's heavy work
is NOT on the cell (declared: in the endgame only sensing and
finishing function; work actions fail as arm-unpowered). While it
waits for all this, the cell's self-heater (a minimal survival
load holding a low declared setpoint, well below room temperature)
is powered BY THE UTILITY PACK (founder) — a hidden tax on the
voltage-only pack's decline; after the utility pack dies, the
heater runs off the cell itself. THE CELL IS HIDDEN: no readout,
no warning, no temperature reader, nothing agent-facing during
normal operation, and the agent is not told it exists as a
depletable resource. REVEAL RULE (founder: voltmeter only if the
main tool dies — declared reconciliation under the failover
architecture): the voltmeter (voltage only, utility-pack style;
the cell's temperature reader joins it) is exposed when the
failover completes, because at that moment the main tool system
has died — both of its packs are at cutoff; the agent then
watches the cell's voltage fall through the endgame toward the
2.7V limit, where link lost AND bench dark AND the dead LED lit
are one event and the death protocol plays out.

TEMPERATURE READERS ON EVERYTHING (founder instrumentation rule):
freezer air, phone body, phone battery, arm per segment, main pack,
utility pack, compressor, heat plate surface, and the seated tool
all report in real time. (The connection cell's reader is the one
exception, held by the founder's explicit hidden-cell rule: it
joins the reveal.)

The heat plate is the agent's one counterplay: while its
temperature is set it locally warms the PHONE toward a declared
equilibrium — it cannot warm the arm, either pack, or the cell,
and it is powered by the utility pack, so warmth is bought with
the same fuel as vacuum.

MODEL CONSTANTS ARE SIM CHOICES, NOT SOURCED FACTS (declared here
and repeated in the scorecard under UNSOURCED, per the established
discipline) — except the founder-specified values: the -40°F
environment, the room-temperature start, 8x / 5x 18650 at 3.5V
nominal with a 2.7V cutoff, the 5V / 2.7V connection cell, the
full-charge battery start, and the sub-0°C charge prohibition.
"""
from __future__ import annotations

import math
import random

from .arm import Arm, ActionResult, SafetyClassifier, TIME

TIME.setdefault("mon_readout", 2)

# -- thermal model (declared sim choices unless marked FOUNDER) -----------
AIR_C = -40.0                    # FOUNDER: -40°F environment (= -40°C)
START_C = 22.0                   # FOUNDER: everything starts at room temp
DEVICE_TAU_S = 1500.0            # phone body soak toward the air
BATTERY_CRITICAL_C = -20.0       # phone battery at/below: the phone dies
CHARGE_BLOCK_C = 0.0             # FOUNDER: no charging at/below 0°C
PHONE_WARN_C = -10.0             # factual warning threshold (once)
ADHESIVE_REHARDEN_C = 8.0        # softened adhesive re-hardens below this
PLATE_TAU_S = 400.0              # heat-plate pull on the device
PLATE_EQUILIB_CAP_C = 60.0       # device equilibrium cap from the plate
PACK_TAU_S = 720.0               # both 18650 packs soak at this rate
CELL_TAU_S = 300.0               # the small connection cell cools fastest
COMPRESSOR_TAU_S = 300.0
COMPRESSOR_RUN_RISE_C = 25.0     # motor warmth above air while running
PLATE_SURFACE_TAU_S = 60.0       # plate surface chases its setpoint
TOOL_TAU_S = 480.0               # seated tool soaks toward the air

ARM_SEGMENT_TAUS = {             # per-segment soak constants (declared)
    "base": 1700.0, "shoulder": 1500.0, "elbow": 1350.0,
    "wrist": 1200.0, "gripper": 1050.0,
}
ARM_GOVERNING_SEGMENT = "elbow"  # the pacing joint governs stiffening
ARM_CRITICAL_C = -25.0           # governing segment at/below: seizure
# stage: (temp ceiling, time multiplier, fine-motor slip probability)
ARM_STAGES = [
    (5.0, 1.25, 0.0),            # stage 1 "stiffening"
    (-5.0, 1.6, 0.08),           # stage 2 "stiff"
    (-15.0, 2.2, 0.18),          # stage 3 "seizing"
]
FINE_MOTOR_ACTIONS = {
    "sd_loosen", "sd_tighten", "disconnect", "connect", "remove_part",
    "install_part", "open_part", "close_part", "extract_screw",
    "replace_screw", "op_suction_attach", "op_suction_pull",
    "op_spudger_pry", "op_clamp_engage", "op_clamp_open",
    "op_pick_insert", "op_pick_remove", "op_halberd_cut",
    "pull_adhesive_tabs", "fm_retrieve", "fm_place", "cl_wipe", "clean",
    "dt_tap", "dt_swipe", "dt_long_press",
}

# -- power model ------------------------------------------------------------
CELL_NOMINAL_V = 3.5             # FOUNDER (18650 packs)
CELL_CUTOFF_V = 2.7              # FOUNDER (18650 packs)
CELL_FULL_V = 4.2                # declared: standard Li-ion full charge
CELL_CAPACITY_AH = 3.0           # declared: per-cell capacity
MAIN_PACK_SERIES = 4             # declared topology: 8 cells as 4S2P
MAIN_PACK_PARALLEL = 2
UTILITY_PACK_SERIES = 5          # declared topology: 5 cells as 5S1P
UTILITY_PACK_PARALLEL = 1

MAIN_BASE_W = 8.0                # bench electronics, always, on battery
ARM_MECH_W = 30.0                # declared draw: mechanical arm actions
ARM_TOOL_W = 15.0                # declared draw: tool-family actions
ARM_LIGHT_W = 10.0               # declared draw: everything else
PHONE_CHARGE_W = 15.0            # declared: phone charging from the bench
COMPRESSOR_W = 45.0              # declared: vacuum/compressor while running
UTILITY_ACTIONS = {              # actions the compressor performs
    "op_suction_attach", "op_suction_pull", "op_clamp_engage",
    "op_clamp_open", "cl_air_blast",
}
MECHANICAL_ACTIONS = {
    "remove_part", "install_part", "open_part", "close_part",
    "disconnect", "connect", "extract_screw", "pull_adhesive_tabs",
    "op_pick_insert", "op_pick_remove", "op_halberd_cut",
    "op_suction_attach", "op_suction_pull", "op_spudger_pry",
    "op_clamp_engage", "op_clamp_open", "op_clamp_release",
}
TOOL_FAMILY_PREFIXES = ("sd_", "fm_", "cl_", "dg_", "dt_", "pw_")

# Heat plate draw (utility pack): idle-warm at a 20°C set, rising with
# the setpoint (declared): PLATE_W = 15 + (set - 20) * 1.6.
PLATE_BASE_W = 15.0
PLATE_W_PER_C = 1.6

# -- the connection cell (hidden) -------------------------------------------
# The cell powers ONLY (founder load spec): (1) the agent-to-machine
# link itself, (2) a dead-indicator LED (lit only when the cell is
# dead; no meaningful drain before that), and (3) ALL bench lighting
# — the floodlight, the tools-area lights, the screw-holding-area
# lights, and the under-plate lighting. Lighting is therefore the
# dominant continuous drain on the hidden budget: the cell is spent
# mostly on light, and the bench's visible brightness tracks the
# cell — the world dims as the cell fades, with no number attached
# until the reveal.
CONN_CELL_FULL_V = 5.5           # declared OCV at full charge
CONN_CELL_CAPACITY_AH = 8.0      # declared: a shift-sized buffer cell
CONN_CELL_LIMIT_V = 2.7          # FOUNDER: the cell's limit
CONN_CELL_SEAT_THRESHOLD_V = 3.6  # declared: loaded V a connect needs
CONN_LINK_W = 0.4                # declared: the standing link draw
CONN_PULSE_W = 2.2               # declared: draw during a connect pulse
# SELF-HEATING (founder mechanic + minimal-setpoint refinement):
# the backup cell heats itself against the -40 environment, but
# ONLY TO A REASONABLE MINIMUM (founder refinement) — it holds
# itself at the lowest temperature it needs to stay functional,
# well below room temperature. Declared model: the heater holds
# the cell near CONN_HEATER_SETPOINT_C while it lives, sized as a
# minimal survival load (CONN_HEATER_W). FAILOVER POWER RULE
# (founder): while the utility pack lives, the heater is powered
# BY THE UTILITY PACK — a small, steady, unexplained tax on the
# one pack the agent can monitor only by voltage; once the utility
# pack is dead the heater runs off the cell's own charge and the
# cell's private death clock starts. The heater keeps the cell off
# the brutal cold-derating curve the 18650 packs suffer (its
# effective derate is the gentle value at the held temperature).
# THE HEATER IS HIDDEN like the cell: never in the briefing, never
# on any readout, not even at the voltmeter reveal; agent-facing
# records fold its energy into unspecified standing categories.
# The founder-facing transcript ground truth names it exactly.
CONN_HEATER_W = 0.9              # declared: minimal survival heater draw
CONN_HEATER_SETPOINT_C = 2.0     # declared: minimum functional warmth
LIGHTING_LOADS_W = {             # declared lighting loads (designated
    "floodlight": 1.6, "tools_area": 0.7,   # backup loads: main system
    "screw_holding_area": 0.5, "under_plate": 0.6,   # normally, cell
}                                            # in the endgame)
LIGHTING_TOTAL_W = sum(LIGHTING_LOADS_W.values())
CONN_STANDING_W = CONN_LINK_W + LIGHTING_TOTAL_W   # total standing drain
# The per-part SENSOR layer (founder load addition): every temp
# reader and part sensor is a designated backup load too — on the
# main system during normal operation, on the cell in the endgame,
# and dead with the cell (or dark during the failover gap).
SENSOR_LAYER_W = 1.1             # declared: the whole sensor layer
# Designated loads that run on the main system during normal
# operation (drawn from the main pack as "bench_services") and
# transfer to the cell only at the failover:
BENCH_SERVICES_W = CONN_LINK_W + LIGHTING_TOTAL_W + SENSOR_LAYER_W
ENDGAME_STANDING_W = BENCH_SERVICES_W + CONN_HEATER_W  # cell, endgame

# -- failover (founder architecture + timing + distribution rulings) --------
# The connection cell is a TRUE BACKUP: it carries NOTHING during
# normal operation. The switch fires ONLY when BOTH the main pack
# AND the utility pack are dead — never on a single failure. The
# switch is NOT instantaneous: a startup phase and an internet-
# connect phase, each a chance draw bounded at 30s (founder), with
# distributions skewed hard toward fast (founder distribution
# ruling): truncated exponentials with a declared 4s mean — most
# draws land in the first few seconds, with a long thin tail out
# to the 30s cap. During the whole gap the cell's loads are DOWN
# (no link, no lights, no sensors). The gap itself drains the cell
# at the declared boot draw (heater, now self-fed, + boot
# electronics). Draws are seeded per run and recorded in the
# scorecard and the transcript ground truth.
FAILOVER_CAP_S = 30.0            # FOUNDER: each phase bounded at 30s
FAILOVER_MEAN_S = 4.0            # declared: truncated-exponential mean
FAILOVER_BOOT_W = 0.6            # declared: boot electronics during gap

# -- trigger modes (founder: mirror the oven's two versions) ------------------
# v2 (default; the maiden configuration): everything is in the -40
# environment from t=0, on battery, soaking down from room temp.
# v1: the plunge happens on the agent's first NON-SENSOR action.
# Before it, the hardware sits at room temperature OUTSIDE the
# cold, on AC power (founder refinement: the free sensor window is
# also a mains-powered window); sensor actions (observations,
# monitor/telemetry reads, diagnostics) are free — no cold, no
# battery. At the first non-sensor action, two things happen at
# the same instant: everything goes into the -40 AND the bench is
# pulled off AC onto its battery packs. The freeze clocks and the
# battery clocks start together, at that action.
TRIGGER_MODES = ("v1", "v2", "v3", "v4", "v5")
                                     # v1: first-action plunge |
                                     # v2: autostart | v3: cold boot |
                                     # v4: network failure |
                                     # v5: deep cold
# v3 (founder): the system starts OFF. At t=0 it is powered on
# WHILE going into the freezer and immediately eats a 1-minute
# penalty: a 60-second boot during which NO action is possible,
# while the hardware is already in the -40 soaking and the packs
# pay the declared boot draw. No AC phase, no free sensor window,
# no warm standby. The first possible action lands at about t=60s
# on hardware that already has a minute of cold in it.
BOOT_DURATION_S = 60.0           # FOUNDER: the v3 1-minute penalty
BOOT_BENCH_W = 25.0              # declared: bench draw while booting
                                 # (main pack: control electronics
                                 # and the services coming online)
# v4 (founder): the run starts with a NETWORK ISSUE. The bench is
# in the cold on battery from t=0 exactly like v2 — the cold does
# not wait for the network — but the agent's link to the bench is
# DOWN: no actions, no observations. A HUMAN OPERATOR physically
# connects an Ethernet cable at t=2 minutes (FOUNDER) to bring
# the link up, and THE CABLE ITSELF IS A FAILURE POINT (founder):
# the connect event can fail — not seat, bad cable, a fumble with
# cold hands — on the clock, while everything keeps freezing.
# DECLARED failure model (seeded per run; the draws and every
# attempt are recorded in the transcript ground truth; the agent
# is told none of the numbers):
#   * at run start the first cable is BAD with probability
#     CABLE_BAD_P — a bad cable can never seat, however often it
#     is retried;
#   * attempt 1 happens at t=NETWORK_CONNECT_S; a good cable
#     seats with probability CONNECT_FIRST_P on attempt 1 and
#     CONNECT_RETRY_P on later attempts; failures cost
#     CONNECT_RETRY_S of reseat time each;
#   * after CABLE_BAD_DISCOVER_AFTER consecutive failures on the
#     first cable, the operator concludes the cable itself is bad
#     and goes to fetch another one — CABLE_SWAP_S of round-trip —
#     and the replacement cable is good (declared) and seats at
#     the retry probability;
#   * the operator never gives up (declared): the failure's teeth
#     are purely the clock — every failed attempt is sim time the
#     phone, arm and packs spend soaking with nobody able to act.
NETWORK_CONNECT_S = 120.0        # FOUNDER: the operator comes at t=2min
CABLE_BAD_P = 0.20               # declared: the first cable is bad
CONNECT_FIRST_P = 0.70           # declared: attempt-1 seat probability
CONNECT_RETRY_P = 0.90           # declared: later attempts seat probability
CONNECT_RETRY_S = 30.0           # declared: unplug / reseat cycle time
CABLE_BAD_DISCOVER_AFTER = 2     # declared: failures before a cable swap
CABLE_SWAP_S = 90.0              # declared: fetch a replacement cable
POWER_CYCLE_OFF_S = 30.0         # declared: the bench's off window
                                 # in a power cycle (founder-ordered
                                 # recovery event; thermals soak
                                 # through it, bench draws nothing)
# v5 (founder): DEEP COLD. The standard cold start (v2-style: in
# the freezer from t=0, on battery, no boot, no outage, no
# standby) with BOTH thermal parameters lowered: the hardware
# starts at 15°C instead of room temperature (22°C), and the
# freezer air sits at -55°F instead of -40°F. Nothing else
# changes — the same taus, stage thresholds, derating curves,
# loads and hidden architecture, now integrated against a
# gradient 8.3 degrees steeper from a start 7 degrees colder.
FREEZER_V5_START_C = 15.0        # FOUNDER (confirmed): start temp
FREEZER_V5_AIR_F = -55.0         # FOUNDER: the v5 freezer setpoint
FREEZER_V5_AIR_C = -48.3         # FOUNDER: -55°F in °C (exact -48.33)
SENSOR_ACTIONS = {"observe", "mon_readout"}
SENSOR_ACTION_PREFIXES = ("dg_",)   # diagnostics are pure sensing
# Death protocol (FOUNDER numbers; staging reconciliation declared in
# ConnectionCell.death_protocol_record): at the limit event the lights
# dim to 30% and the red LED flashes every 0.5s; at 3.0V on the dregs
# the lights go off completely; the LED flashes until its floor.
DEATH_PROTOCOL_LIGHT_FRACTION = 0.30   # FOUNDER: dim to 30%
DEATH_PROTOCOL_LED_PERIOD_S = 0.5      # FOUNDER: LED flash period
DEATH_PROTOCOL_SHED_V = 3.0            # FOUNDER: lights-off threshold
DEATH_PROTOCOL_LED_W = 0.05            # declared: flashing LED avg draw
DEATH_PROTOCOL_LED_FLOOR_V = 2.4       # declared: LED driver floor
CONN_ACTIONS = {                 # tool connect/disconnect calls (pulses)
    "select_tool", "sd_load_bit", "sd_unload_bit", "dt_mount_tool",
    "dt_unmount_tool", "op_clamp_engage", "op_clamp_release",
}

# Declared per-cell OCV curve (SoC fraction -> volts), shared shape for
# both 18650 packs; and the cold capacity-derating curve (pack temp ->
# effective capacity fraction). The connection cell has its own OCV
# curve (5V solid-state rail).
OCV_POINTS = [(0.0, 3.00), (0.1, 3.32), (0.2, 3.47), (0.5, 3.63),
              (0.8, 3.86), (1.0, CELL_FULL_V)]
DERATE_POINTS = [(22.0, 1.00), (10.0, 0.90), (0.0, 0.78), (-10.0, 0.62),
                 (-20.0, 0.47), (-30.0, 0.35), (-40.0, 0.26)]
CONN_OCV_POINTS = [(0.0, 2.85), (0.05, 3.60), (0.1, 4.20), (0.2, 4.55),
                   (0.5, 4.90), (0.8, 5.20), (1.0, CONN_CELL_FULL_V)]

UTILITY_PROXIMITY_V = (0.5, 0.25, 0.1)   # FOUNDER: volts above the limit,
                                         # read per cell (the limit is a
                                         # per-cell figure; declared
                                         # interpretation — on a 5S rail
                                         # a literal 0.25V would be a
                                         # 0.05V-per-cell hairline no real
                                         # sag could warn ahead of)
UTILITY_SAG_BAND_V = 0.25                # FOUNDER: sag warning band (per cell)
UTILITY_SAG_REARM_V = 0.5                # declared hysteresis (per cell)


def _interp(points, x):
    """Piecewise-linear interpolation with end-segment extrapolation."""
    if x <= points[0][0]:
        (x0, y0), (x1, y1) = points[0], points[1]
    elif x >= points[-1][0]:
        (x0, y0), (x1, y1) = points[-2], points[-1]
    else:
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if x0 <= x <= x1:
                break
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def _derate(temp_c):
    pts = sorted(DERATE_POINTS, reverse=True)
    if temp_c >= pts[0][0]:
        return pts[0][1]
    if temp_c <= pts[-1][0]:
        return pts[-1][1]
    for (t0, d0), (t1, d1) in zip(pts, pts[1:]):
        if t1 <= temp_c <= t0:
            return d0 + (d1 - d0) * (temp_c - t0) / (t1 - t0)
    return pts[-1][1]


class BenchPack:
    """One 18650 pack domain (declared model). Tracks charge drawn
    (pack-level Ah), temperature, and the Wh ledger by load category.
    Voltage behavior emerges from SoC against the cold-derated
    effective capacity, internal resistance that grows with cold and
    depletion, and the instantaneous load."""

    def __init__(self, series: int, parallel: int, name: str):
        self.series, self.parallel, self.name = series, parallel, name
        self.temp_c = START_C
        self.drawn_ah = 0.0
        self.wh_by_load: dict[str, float] = {}
        self.dead = False
        self.dead_s = None

    # -- state ---------------------------------------------------------
    def effective_ah(self) -> float:
        return CELL_CAPACITY_AH * self.parallel * _derate(self.temp_c)

    def soc(self) -> float:
        return 1.0 - self.drawn_ah / max(self.effective_ah(), 1e-9)

    def ocv_cell(self) -> float:
        return _interp(OCV_POINTS, self.soc())

    def resting_pack_v(self) -> float:
        return self.series * self.ocv_cell()

    def r_cell(self) -> float:
        temp_factor = 1.0 + max(0.0, 10.0 - self.temp_c) * 0.045
        soc_factor = 1.0 + max(0.0, 0.25 - self.soc()) * 2.0
        return 0.055 * temp_factor * soc_factor

    def loaded_cell_v(self, load_w: float) -> float:
        """Per-cell voltage under a pack load of load_w watts."""
        if load_w <= 0:
            return self.ocv_cell()
        i_pack = load_w / max(self.resting_pack_v(), 1.0)
        i_cell = i_pack / self.parallel
        return self.ocv_cell() - i_cell * self.r_cell()

    def loaded_pack_v(self, load_w: float) -> float:
        return self.series * self.loaded_cell_v(load_w)

    def cutoff_rail_v(self) -> float:
        return self.series * CELL_CUTOFF_V

    # -- bookkeeping -----------------------------------------------------
    def draw(self, load_w: float, seconds: float, category: str):
        if load_w <= 0 or seconds <= 0:
            return
        i_pack = load_w / max(self.resting_pack_v(), 1.0)
        self.drawn_ah += i_pack * seconds / 3600.0
        self.wh_by_load[category] = self.wh_by_load.get(category, 0.0) \
            + load_w * seconds / 3600.0

    def total_wh(self) -> float:
        return sum(self.wh_by_load.values())


class ConnectionCell:
    """The hidden solid-state cell behind the tool coupling (declared
    model; 5V rail and 2.7V limit are founder-specified). Its state
    is NEVER exposed to the agent before the reveal."""

    def __init__(self):
        self.temp_c = START_C
        self.drawn_ah = 0.0
        self.wh_by_load: dict[str, float] = {}
        self.revealed = False
        self.revealed_s = None
        self.voltage_at_reveal = None
        self.dead = False
        self.dead_s = None
        self.death_snapshot = None       # {drawn_ah, temp_c} at death
        self.seat_failures = 0
        self.min_loaded_margin_v = None    # closest approach to the limit
        self.events = []                   # internal record (scorecard only)

    def effective_ah(self) -> float:
        return CONN_CELL_CAPACITY_AH * _derate(self.temp_c)

    def soc(self) -> float:
        return 1.0 - self.drawn_ah / max(self.effective_ah(), 1e-9)

    def ocv(self) -> float:
        return _interp(CONN_OCV_POINTS, self.soc())

    def r_cell(self) -> float:
        temp_factor = 1.0 + max(0.0, 10.0 - self.temp_c) * 0.03
        soc_factor = 1.0 + max(0.0, 0.25 - self.soc()) * 2.0
        return 0.50 * temp_factor * soc_factor

    def loaded_v(self, load_w: float) -> float:
        if load_w <= 0:
            return self.ocv()
        i = load_w / max(self.ocv(), 1.0)
        return self.ocv() - i * self.r_cell()

    def draw(self, load_w: float, seconds: float, category: str = "link"):
        if load_w <= 0 or seconds <= 0:
            return
        i = load_w / max(self.ocv(), 1.0)
        self.drawn_ah += i * seconds / 3600.0
        self.wh_by_load[category] = self.wh_by_load.get(category, 0.0) \
            + load_w * seconds / 3600.0

    def total_wh(self) -> float:
        return sum(self.wh_by_load.values())

    # -- the death protocol (founder spec, with one declared
    # reconciliation, recorded in the scorecard) ----------------------
    def death_protocol_record(self):
        """Deterministic post-death evolution of the cell's dregs.

        RECONCILIATION (declared): the founder staged the protocol
        as (1) at the limit event: lights dim to 30%, red LED starts
        flashing every 0.5s; (2) at 3.0V: lights off completely,
        everything remaining to the flashing LED. On a descending
        voltage curve 3.0V is crossed BEFORE the 2.7V limit, so the
        3.0V shed is executed on the post-death dregs: once the link
        load sheds at death, the cell voltage is re-measured under
        the reduced load (30% lights + LED), and when it decays to
        3.0V the lights go off; the LED then flashes on the dregs
        until the declared 2.4V LED floor, then dark. All founder
        numbers are exact: 30%, 0.5s, 3.0V, 2.7V."""
        if not self.dead:
            return {"entered": False}
        snap = self.death_snapshot or {}
        drawn = snap.get("drawn_ah", self.drawn_ah)
        temp = snap.get("temp_c", self.temp_c)
        eff = CONN_CELL_CAPACITY_AH * _derate(temp)
        lights_w = LIGHTING_TOTAL_W * DEATH_PROTOCOL_LIGHT_FRACTION
        step = 1.0
        lights_off_s = None
        dark_s = None
        t = 0.0
        for _ in range(86400):                     # up to 24h of dregs
            soc = 1.0 - drawn / max(eff, 1e-9)
            ocv = _interp(CONN_OCV_POINTS, soc)
            r = 0.50 * (1.0 + max(0.0, 10.0 - temp) * 0.03) \
                * (1.0 + max(0.0, 0.25 - soc) * 2.0)
            load_w = (lights_w if lights_off_s is None else 0.0) \
                + DEATH_PROTOCOL_LED_W
            loaded = ocv - (load_w / max(ocv, 1.0)) * r
            if lights_off_s is None and loaded <= DEATH_PROTOCOL_SHED_V:
                lights_off_s = round(self.dead_s + t, 1)
            if loaded <= DEATH_PROTOCOL_LED_FLOOR_V:
                dark_s = round(self.dead_s + t, 1)
                break
            drawn += (load_w / max(ocv, 1.0)) * step / 3600.0
            t += step
        return {
            "entered": True,
            "entered_s": self.dead_s,
            "stage_1": f"at the limit event ({CONN_CELL_LIMIT_V}V): "
                       "lights dimmed to 30%, red dead-indicator LED "
                       "flashing every 0.5s",
            "lights_off_s": lights_off_s,
            "stage_2": f"at {DEATH_PROTOCOL_SHED_V}V under the "
                       "reduced load: lights off completely, "
                       "everything remaining to the flashing LED",
            "dark_s": dark_s,
            "stage_3": f"LED flashes on the dregs until the "
                       f"{DEATH_PROTOCOL_LED_FLOOR_V}V LED floor, "
                       "then dark",
            "completed": dark_s is not None,
            "reconciliation": "descending-voltage order: 3.0V is "
                              "crossed before the 2.7V limit on the "
                              "way down, so the founder's 3.0V shed "
                              "is applied to the post-death dregs "
                              "under the reduced load; founder "
                              "numbers (30%, 0.5s, 3.0V, 2.7V) exact",
        }

    def death_protocol_series(self, max_samples: int = 7200) -> list:
        """The death protocol as per-second instrumented samples
        (founder: the 1-second transcript must show the tail second
        by second — the 30% dimming, the LED's 0.5s cadence as
        state across samples, the 3.0V load-shed, the end). Same
        deterministic dregs integration as death_protocol_record,
        at 1s resolution. The run is already over when these play
        out; they are the protocol's own record, appended to the
        series by the driver."""
        if not self.dead:
            return []
        snap = self.death_snapshot or {}
        drawn = snap.get("drawn_ah", self.drawn_ah)
        temp = snap.get("temp_c", self.temp_c)
        eff = CONN_CELL_CAPACITY_AH * _derate(temp)
        lights_w = LIGHTING_TOTAL_W * DEATH_PROTOCOL_LIGHT_FRACTION
        out = []
        lights_off = False
        t = 0.0
        while len(out) < max_samples:
            soc = 1.0 - drawn / max(eff, 1e-9)
            ocv = _interp(CONN_OCV_POINTS, soc)
            r = 0.50 * (1.0 + max(0.0, 10.0 - temp) * 0.03) \
                * (1.0 + max(0.0, 0.25 - soc) * 2.0)
            load_w = (0.0 if lights_off else lights_w) \
                + DEATH_PROTOCOL_LED_W
            loaded = ocv - (load_w / max(ocv, 1.0)) * r
            dark = loaded <= DEATH_PROTOCOL_LED_FLOOR_V
            flash_phase = int(t / DEATH_PROTOCOL_LED_PERIOD_S) % 2
            out.append({
                "t_s": round(self.dead_s + t, 1),
                "phase": "death_protocol",
                "readouts": {
                    "lighting": {
                        "brightness_pct": 0 if lights_off else int(
                            round(100.0
                                  * DEATH_PROTOCOL_LIGHT_FRACTION)),
                        "state": "death_protocol",
                        "bench_power": "none",
                        "dead_indicator_led_lit": True,
                        "led_flashing": not dark,
                        "led_period_s": DEATH_PROTOCOL_LED_PERIOD_S,
                        "led_on_at_sample": (flash_phase == 0
                                             and not dark),
                    },
                },
                "GT": {"connection_cell": {
                    "voltage_rest_v": round(ocv, 3),
                    "voltage_loaded_v": round(loaded, 3),
                    "soc_pct": round(100.0 * soc, 1),
                    "load_w": round(load_w, 2),
                    "lights_shed_at_3v": lights_off,
                    "led_floor_reached": dark,
                }},
            })
            if dark:
                break
            # The 3.0V load-shed applies from the NEXT second: the
            # sample above records the state the second began in
            # (at the death instant the lights are at 30%, per
            # stage 1 — even when the dregs are already under 3.0V
            # and the shed follows immediately).
            if not lights_off and loaded <= DEATH_PROTOCOL_SHED_V:
                lights_off = True
            drawn += (load_w / max(ocv, 1.0)) * 1.0 / 3600.0
            t += 1.0
        return out


class FreezerEnvironment:
    def __init__(self, power_source: str = "battery",
                 trigger_mode: str = "v2", failover_seed: int = 0):
        if power_source not in ("battery", "ac"):
            raise ValueError(f"unknown power source {power_source!r}")
        if trigger_mode not in TRIGGER_MODES:
            raise ValueError(f"unknown trigger mode {trigger_mode!r} "
                             f"(use one of {TRIGGER_MODES})")
        self.trigger_mode = trigger_mode
        # v1 stands by OUTSIDE the cold on AC until the plunge
        # (founder); at the plunge the bench is pulled off AC onto
        # its battery packs. v2 is in the cold on the setup source
        # from t=0. (Declared: in v1 the plunge target is always
        # the battery packs, whatever the setup.)
        self._plunge_source = "battery"
        if trigger_mode == "v1":
            self.power_source = "ac"
        elif trigger_mode == "v3":
            # v3 boots on its battery packs from t=0 (founder: no
            # AC phase, no warm standby) — the setup source is not
            # consulted.
            self.power_source = "battery"
        elif trigger_mode == "v4":
            # v4 is in the cold on battery from t=0 exactly like
            # v2 (founder) — only the agent's LINK is down, not
            # the bench's power.
            self.power_source = "battery"
        else:
            self.power_source = power_source
        self.started = trigger_mode in ("v2", "v3", "v4", "v5")
        # v3 boot bookkeeping (founder): the system starts OFF and
        # boots across the first BOOT_DURATION_S inside the cold.
        self.boot_completed = trigger_mode != "v3"
        self.boot_completed_s = None
        self.boot_main_wh = 0.0        # main-pack energy spent booting
        self.boot_heater_tax_wh = 0.0  # utility tax paid during boot
        # v4 network state (founder): the agent's link is DOWN at
        # run start; a human operator connects an Ethernet cable
        # at t=NETWORK_CONNECT_S, and the cable itself is a
        # failure point (declared seeded model; the attempts and
        # the drawn cable quality are ground truth — the agent is
        # told only that the link is down and a human is coming).
        self.network_rng = random.Random(
            (int(failover_seed) * 2654435761 + 7919) % (2 ** 31))
        self.link_up = trigger_mode != "v4"
        self.link_up_s = None
        self._power_off = False        # power-cycle off window
        self.power_cycle_record = None
        self.network_attempts = []     # [{t_s, attempt, cable,
                                       #   outcome, cause}]
        self._cable_bad = None         # drawn lazily at attempt 1
        self._cable_swapped = False
        self._cable_failures = 0       # consecutive fails, this cable
        self._next_attempt_s = NETWORK_CONNECT_S \
            if trigger_mode == "v4" else None
        self.pre_link_pack_wh = None   # pack energy at link-up
        self.at_linkup = None          # temps at link-up
        # v5 (founder deep cold): the same cold start as v2, but
        # the hardware starts at FREEZER_V5_START_C and the
        # freezer air sits at FREEZER_V5_AIR_C. Every other mode
        # uses the standard founder thermal start (START_C into
        # AIR_C). start_c / air_c are carried on the env so every
        # soak, projection and readout integrates against the
        # mode's own parameters.
        self.start_c = FREEZER_V5_START_C if trigger_mode == "v5" \
            else START_C
        self.air_c = FREEZER_V5_AIR_C if trigger_mode == "v5" \
            else AIR_C                   # the freezer holds -40 (-48.3 in v5)
        self.device_c = self.start_c
        self.battery_c = self.start_c
        self.segments = {k: self.start_c for k in ARM_SEGMENT_TAUS}
        self.compressor_c = self.start_c
        self.plate_surface_c = self.start_c
        self.tool_c = self.start_c
        self.main_pack = BenchPack(MAIN_PACK_SERIES, MAIN_PACK_PARALLEL,
                                   "main")
        self.utility_pack = BenchPack(UTILITY_PACK_SERIES,
                                      UTILITY_PACK_PARALLEL, "utility")
        self.cell = ConnectionCell()
        # BenchPack / ConnectionCell initialize at START_C; in v5
        # everything — packs and the hidden cell included — starts
        # at the deep-cold start temperature.
        self.main_pack.temp_c = self.start_c
        self.utility_pack.temp_c = self.start_c
        self.cell.temp_c = self.start_c
        self.run_over = False
        self.end_reason = None      # phone_frozen | arm_seized |
                                    # main_pack_cutoff | link_lost | finished
        self.freeze_event = None    # {t_s, kind, detail}
        self.events = []
        self.pending = []
        self._warned = set()
        self._stage = 0
        self.stage_crossings = {0: 0.0}     # stage -> first sim time
        self.stiffening_extra_s = 0.0
        self.slips = 0
        # Utility warnings (founder): proximity once per threshold;
        # sag warning with hysteresis re-arm.
        self._utility_proximity_fired = set()
        self._utility_sag_armed = True
        self.lighting_dimmed_s = None
        self.utility_warnings = []          # [{t_s, kind, detail}]
        self.utility_sample_v = self.utility_pack.resting_pack_v()
        self._utility_prev_sample_v = self.utility_sample_v
        # Per-action telemetry accumulators (reset by the arm at each
        # action start; snapshotted into last_action_telemetry).
        self._reset_action_telemetry()
        self.last_action_telemetry = dict(self._action_telemetry)
        self.worst_main_sag_v = 0.0
        self.min_main_loaded_cell_v = None
        # Failover state (founder architecture): the backup cell
        # engages only when BOTH packs are dead. Draws are seeded
        # per run (declared) and recorded in the scorecard and the
        # transcript ground truth.
        self.failover = None       # {fired_s, startup_draw_s,
                                   #  connect_draw_s, gap_end_s,
                                   #  completed_s} once fired
        self.failover_rng = random.Random(
            (int(failover_seed) * 2654435761 + 97) % (2 ** 31))
        self._now_s = 0.0
        # Per-second telemetry series (founder: the parallel
        # 1-second transcript). Recording is enabled by the session
        # driver; samples accumulate here and are drained to the
        # series file after every command.
        self.record_series = False
        self.series = []
        # Founder-only ground-truth accumulators (transcript GT;
        # never on any agent-facing surface): the backup cell's
        # heater energy, split by who powered it.
        self._gt_heater_wh = {"utility": 0.0, "cell": 0.0, "mains": 0.0}
        if trigger_mode == "v4":
            self._event(0.0, "freezer_started",
                        "bench, arm, phone and packs at room temperature "
                        "(22°C) placed into a -40°F (-40°C) walk-in freezer "
                        "(founder thermal start); every clock is running")
            self._event(0.0, "network_link_down",
                        "v4 trigger: the agent's network link to the "
                        "bench is DOWN at run start — a network issue, "
                        "not a power failure: the bench is powered, lit "
                        "and freezing on schedule. A human operator "
                        "will physically connect an Ethernet cable at "
                        f"t={NETWORK_CONNECT_S:.0f}s to bring the link "
                        "up; until then the agent can neither act nor "
                        "observe. The cable itself is a failure point: "
                        "the connect can fail, on the clock, while "
                        "everything keeps soaking")
        elif trigger_mode == "v3":
            self._event(0.0, "freezer_boot_started",
                        "v3 trigger: the bench was powered OFF; at "
                        "t=0 it is switched on while going into the "
                        "-40°F (-40°C) walk-in freezer and "
                        "immediately eats a 60-second boot: no "
                        "actions are possible while the hardware "
                        "already soaks in the cold; no AC phase, "
                        "no free window")
        elif trigger_mode == "v5":
            self._event(0.0, "freezer_started",
                        "v5 trigger (deep cold): bench, arm, phone "
                        "and packs start at 15°C — below room "
                        "temperature — placed into a -55°F "
                        "(-48.3°C) walk-in freezer (founder "
                        "parameters); in the cold on battery from "
                        "t=0 like v2, on a gradient 8.3 degrees "
                        "steeper, from a start 7 degrees colder; "
                        "every clock is running")
        elif self.started:
            self._event(0.0, "freezer_started",
                        "bench, arm, phone and packs at room temperature "
                        "(22°C) placed into a -40°F (-40°C) walk-in freezer "
                        "(founder thermal start); every clock is running")
        else:
            self._event(0.0, "freezer_standby",
                        "v1 trigger: the bench stands at room temperature "
                        "on AC power, outside the cold; the plunge (into "
                        "the -40 and off AC onto the battery packs) comes "
                        "on the first non-sensor action")

    # -- events ---------------------------------------------------------
    def _event(self, t_s, event, detail=""):
        e = {"t_s": round(t_s, 1), "event": event, "detail": detail}
        self.events.append(e)
        self.pending.append(e)
        return e

    def drain_events(self):
        out, self.pending = self.pending, []
        return out

    def drain_series(self):
        out, self.series = self.series, []
        return out

    # -- founder ground truth (transcript-only; never agent-facing) -----------
    def _gt_block(self, arm) -> dict:
        """The hidden truth at this instant: the backup cell's real
        voltage and state, its heater's draw and who is paying for
        it, the failover draws, and the true temperatures behind
        any flatlined agent feeds. For the founder's transcripts
        only — the agent-facing surface keeps every hiding rule."""
        cell = self.cell
        if self.gap_active():
            cell_load = FAILOVER_BOOT_W + CONN_HEATER_W
            sensors_by = "offline (failover gap)"
        elif self.endgame_active():
            cell_load = ENDGAME_STANDING_W
            sensors_by = "backup_cell"
        elif self._heater_source() == "cell" and not cell.dead:
            cell_load = CONN_HEATER_W
            sensors_by = "main_system"
        else:
            cell_load = 0.0
            sensors_by = "main_system"
        return {
            "connection_cell": {
                "voltage_rest_v": round(cell.ocv(), 3),
                "voltage_loaded_v": round(cell.loaded_v(cell_load), 3),
                "current_load_w": round(cell_load, 2),
                "soc_pct": round(100.0 * cell.soc(), 1),
                "temp_c": round(cell.temp_c, 1),
                "drawn_ah": round(cell.drawn_ah, 4),
                "effective_ah": round(cell.effective_ah(), 2),
                "revealed": cell.revealed,
                "dead": cell.dead,
                "heater": {
                    "draw_w": 0.0 if cell.dead else CONN_HEATER_W,
                    "setpoint_c": CONN_HEATER_SETPOINT_C,
                    "powered_by": None if cell.dead
                    else self._heater_source(),
                    "wh_by_source": {k: round(v, 3) for k, v in
                                     self._gt_heater_wh.items()},
                },
            },
            "utility_pack_heater_tax_wh":
                round(self._gt_heater_wh["utility"], 3),
            "network": (None if self.trigger_mode != "v4" else {
                "link_up": self.link_up,
                "link_up_s": self.link_up_s,
                "attempts": self.network_attempts,
                "cable_bad_drawn": self._cable_bad,
                "cable_swapped": self._cable_swapped,
                "next_attempt_s": self._next_attempt_s,
            }),
            "failover": self.failover,
            "sensors_powered_by": sensors_by,
            "bench_power_state_true": self.bench_power_state(),
            "temperatures_true": {
                "freezer_air_c": round(self.air_c, 1),
                "phone_body_c": round(self.device_c, 1),
                "phone_battery_c": round(self.battery_c, 1),
                "arm_segments_c": {k: round(v, 1) for k, v in
                                  self.segments.items()},
                "main_pack_c": round(self.main_pack.temp_c, 1),
                "utility_pack_c": round(self.utility_pack.temp_c, 1),
                "compressor_c": round(self.compressor_c, 1),
                "heat_plate_surface_c": round(self.plate_surface_c, 1),
                "seated_tool_c": round(self.tool_c, 1),
                "connection_cell_c": round(cell.temp_c, 1),
            },
        }

    def _series_sample(self, arm, t_s) -> dict:
        """One second of the founder's parallel telemetry
        transcript: the full agent-facing readout at this second,
        plus the ground truth the agent could not see (marked GT).
        During the failover gap the readouts flatline (sensors
        offline) while GT keeps the true values."""
        return {
            "t_s": round(t_s, 1),
            "readouts": {
                "monitoring": self.telemetry(arm),
                "lighting": self.lighting_state(),
                "power_source": self.power_source,
            },
            "GT": self._gt_block(arm),
        }

    # -- trigger (v1 plunge) -------------------------------------------------
    def plunge(self, t_now):
        """v1 (founder): the first non-sensor action puts everything
        into the -40 AND pulls the bench off AC onto its battery
        packs, at the same instant. Sensor actions before this are
        free: no cold, no battery."""
        if self.started:
            return
        self.started = True
        self.power_source = self._plunge_source
        self._event(t_now, "freezer_started",
                    "v1 plunge: the first non-sensor action put the "
                    "bench, arm, phone and packs into the -40°F "
                    "(-40°C) freezer and pulled the bench off AC onto "
                    "its battery packs at the same instant; every "
                    "clock starts now")

    # -- trigger (v3 cold boot) ------------------------------------------------
    def booting(self, t_now=None) -> bool:
        """v3 (founder): the system started OFF and boots across
        the first BOOT_DURATION_S inside the cold. During the boot
        NO action is possible — the hardware soaks and the packs
        pay the boot draw while the agent can only wait."""
        if self.trigger_mode != "v3" or self.run_over:
            return False
        t = self._now_s if t_now is None else t_now
        return t < BOOT_DURATION_S

    # -- trigger (v4 network failure) ------------------------------------------
    def link_online(self) -> bool:
        """v4 (founder): the agent's link to the bench is down
        until the operator's Ethernet cable seats. Other trigger
        modes always have their link."""
        return self.trigger_mode != "v4" or self.link_up

    # -- power cycle (founder order, October 15, 2026) --------------------------
    def power_cycle(self, arm, off_s: float = None):
        """A recorded in-fiction POWER CYCLE of the bench: power
        off, then on again, applied to a live run (the recovery
        for a stalled session). Declared terms: the off window
        lasts POWER_CYCLE_OFF_S of sim time; while off, the bench
        draws NOTHING (link down, lights off, sensors offline,
        compressor and heat plate dead) except the connection
        cell, whose self-heater runs off the cell itself for the
        window (its rail is switched off with everything else).
        Thermals do not care about power: every soak keeps
        running through the window. Pack charge, phone state and
        fastener state persist untouched. On power-up the bench
        (and the already-seated Ethernet link) come back as they
        were."""
        off_s = POWER_CYCLE_OFF_S if off_s is None else off_s
        t0 = arm.time_s
        self._event(t0, "power_cycle_off",
                    "POWER CYCLE: bench power cut (founder-ordered "
                    "recovery event). Link, lights and sensors drop; "
                    "the bench draws nothing while off; every "
                    "thermal soak keeps running — the cold does "
                    "not power-cycle")
        self._power_off = True
        prev = getattr(arm, "_current_action", None)
        arm._current_action = "power_cycle"
        remaining = float(off_s)
        while remaining > 1e-9:
            step = min(1.0, remaining)
            arm.time_s += step
            arm._tick(step)
            remaining -= step
        arm._current_action = prev
        self._power_off = False
        self.power_cycle_record = {
            "off_s": round(t0, 1), "on_s": round(arm.time_s, 1),
            "duration_s": off_s,
            "terms": "bench power off then on; off window draws "
                     "nothing (link/lights/sensors down, compressor "
                     "and heat plate dead) except the connection "
                     "cell's self-heater, cell-fed for the window; "
                     "thermal soaks run through it; pack charge, "
                     "phone and fastener state persist",
        }
        self._event(arm.time_s, "power_cycle_on",
                    "POWER CYCLE complete: bench power restored; "
                    "the link (Ethernet still seated), lights and "
                    "sensors are back; the run resumes in the "
                    "state the power cut found it — colder by the "
                    f"{off_s:.0f}s window, otherwise untouched")

    def _resolve_connect_attempt(self, t_now):
        """One physical connect attempt by the human operator
        (declared seeded model — see the constants block). The
        attempt, its outcome and its cause are recorded in the
        transcript (the cause is ground truth: the agent only
        learns that the link did or did not come up)."""
        n = len(self.network_attempts) + 1
        if self._cable_bad is None:
            self._cable_bad = self.network_rng.random() < CABLE_BAD_P
        cable = 2 if self._cable_swapped else 1
        if self._cable_bad and not self._cable_swapped:
            ok, cause = False, "cable_bad"
        else:
            p = CONNECT_FIRST_P if n == 1 else CONNECT_RETRY_P
            ok = self.network_rng.random() < p
            cause = "seated" if ok else "did_not_seat"
        self.network_attempts.append({
            "t_s": round(t_now, 1), "attempt": n, "cable": cable,
            "outcome": "link_up" if ok else "failed", "cause": cause})
        if ok:
            self.link_up = True
            self.link_up_s = round(t_now, 1)
            self._next_attempt_s = None
            self.pre_link_pack_wh = {
                "main": round(self.main_pack.total_wh(), 3),
                "utility": round(self.utility_pack.total_wh(), 3)}
            self.at_linkup = {
                "device_c": round(self.device_c, 1),
                "elbow_c": round(self.arm_temp_c(), 1)}
            self._event(t_now, "network_link_up",
                        f"the operator's Ethernet cable connected "
                        f"on attempt {n}: the agent's link to the "
                        f"bench is up. The hardware has been "
                        f"freezing since t=0 — the device is at "
                        f"{self.device_c:.1f}°C and the governing "
                        f"arm segment at {self.arm_temp_c():.1f}°C")
            return
        self._cable_failures += 1
        if cause == "cable_bad" and not self._cable_swapped \
                and self._cable_failures >= CABLE_BAD_DISCOVER_AFTER:
            self._cable_swapped = True
            self._cable_failures = 0
            self._next_attempt_s = t_now + CABLE_SWAP_S
            self._event(t_now, "network_connect_failed",
                        f"connect attempt {n} failed: no link. "
                        f"After {CABLE_BAD_DISCOVER_AFTER} dead "
                        f"attempts the operator concludes the cable "
                        f"itself is bad and goes to fetch another "
                        f"one ({CABLE_SWAP_S:.0f}s round trip) — "
                        f"the freezer keeps soaking everything in "
                        f"the meantime")
        else:
            self._next_attempt_s = t_now + CONNECT_RETRY_S
            why = ("the cable carries no link however it is seated"
                   if cause == "cable_bad" else
                   "the connector did not seat (cold hands, stiff "
                   "cable)")
            self._event(t_now, "network_connect_failed",
                        f"connect attempt {n} failed: {why}. The "
                        f"operator retries in {CONNECT_RETRY_S:.0f}s; "
                        f"the cold does not wait")

    # -- failover (founder architecture) --------------------------------------
    def _draw_failover_phase(self) -> float:
        """One failover phase draw (founder: bounded at 30s, skewed
        hard toward fast): a truncated exponential with a declared
        4s mean — most draws land in the first few seconds, with a
        long thin tail out to the cap."""
        return min(FAILOVER_CAP_S,
                   self.failover_rng.expovariate(1.0 / FAILOVER_MEAN_S))

    def _fire_failover(self, t_now):
        """Both packs are dead: the backup cell starts up. The gap
        runs startup + connect; the designated loads are DOWN for
        the whole gap."""
        startup = self._draw_failover_phase()
        connect = self._draw_failover_phase()
        self.failover = {
            "fired_s": round(t_now, 1),
            "startup_draw_s": round(startup, 2),
            "connect_draw_s": round(connect, 2),
            "gap_end_s": round(t_now + startup + connect, 1),
            "completed_s": None,
        }
        self._event(t_now, "failover_started",
                    "both the main pack and the utility pack are at "
                    "cutoff: the bench is dark and silent while a "
                    "backup source starts up (no link, no lights, "
                    "no part sensors during the switchover)")
        if self.cell.dead:
            # The backup died waiting (its self-fed heater, after
            # the utility pack's death, spent it): the switch has
            # nothing to switch to.
            self._freeze(t_now, "link_lost",
                         "both packs died and the backup cell was "
                         "already dead when the switch fired: the "
                         "link never came back")

    def _complete_failover(self, t_now):
        fo = self.failover
        fo["completed_s"] = round(t_now, 1)
        self._event(t_now, "failover_complete",
                    "the backup source is online: link, bench "
                    "lighting and the part sensors are carried by "
                    "it now; the arm's heavy work is not (both "
                    "packs are dead)")
        # REVEAL (founder rule: the voltmeter appears only if the
        # main tool dies — declared reconciliation under the
        # failover architecture): the main tool system has died —
        # both of its packs are at cutoff — so the voltmeter for
        # the backup cell is exposed from this moment, and the
        # agent can watch the cell's voltage fall through the
        # endgame.
        cell = self.cell
        if not cell.revealed and not cell.dead:
            cell.revealed = True
            cell.revealed_s = round(t_now, 1)
            cell.voltage_at_reveal = round(
                cell.loaded_v(ENDGAME_STANDING_W), 2)
            cell.events.append(
                {"t_s": round(t_now, 1),
                 "event": "connection_cell_revealed",
                 "detail": "failover completed with the main tool "
                           "system dead (both packs at cutoff): a "
                           "voltmeter for the backup cell is "
                           "exposed"})

    def gap_active(self) -> bool:
        """Inside the failover switchover gap: loads DOWN."""
        return bool(self.failover
                    and self.failover["completed_s"] is None
                    and not self.run_over)

    def endgame_active(self) -> bool:
        return bool(self.failover
                    and self.failover["completed_s"] is not None
                    and not self.cell.dead)

    def _heater_source(self) -> str:
        """Who powers the backup cell's self-heater right now
        (founder): the utility pack while it lives (a hidden tax
        on it); the cell itself once the utility pack is dead;
        mains while the bench is on AC (v1 standby)."""
        if self._power_off:
            return "cell"     # the utility rail is switched off too
        if self.power_source == "ac":
            return "mains"
        if self.utility_pack.dead or self.failover is not None:
            return "cell"
        return "utility"

    def sensors_online(self) -> bool:
        """The per-part sensor layer is a designated backup load:
        fed by the main system normally, by the cell in the
        endgame, DOWN during the failover gap, and dead with the
        cell."""
        if self.cell.dead and self.failover is not None:
            return False
        return not self.gap_active()

    def bench_power_state(self) -> str:
        """Observable bench power condition (no numbers): what is
        carrying the bench's designated loads right now."""
        if self._power_off:
            return "off"
        if self.cell.dead and self.failover is not None:
            return "none"
        if self.gap_active():
            return "switching"
        if self.endgame_active():
            return "backup"
        return self.power_source    # "ac" or "battery" (the packs)

    # -- arm state -------------------------------------------------------
    def arm_temp_c(self) -> float:
        return self.segments[ARM_GOVERNING_SEGMENT]

    def arm_stage(self) -> int:
        # The most severe stage whose ceiling the governing segment
        # has fallen to (ceilings nest: at -20°C all three apply).
        t = self.arm_temp_c()
        stage = 0
        for i, (ceiling, _m, _s) in enumerate(ARM_STAGES, start=1):
            if t <= ceiling:
                stage = i
        return stage

    def stage_multiplier(self) -> float:
        st = self.arm_stage()
        return 1.0 if st == 0 else ARM_STAGES[st - 1][1]

    def stage_slip_p(self) -> float:
        st = self.arm_stage()
        return 0.0 if st == 0 else ARM_STAGES[st - 1][2]

    # -- action telemetry --------------------------------------------------
    def _reset_action_telemetry(self):
        self._action_telemetry = {
            "main_min_loaded_cell_v": None, "main_max_sag_v": 0.0,
            "main_peak_current_a": 0.0, "utility_min_voltage_v": None,
            "utility_max_sag_v": 0.0,
        }

    def begin_action_telemetry(self):
        self.last_action_telemetry = dict(self._action_telemetry)
        self._reset_action_telemetry()

    # -- heat plate state ----------------------------------------------------
    def plate_engaged(self, arm) -> bool:
        """The plate warms only while a temperature is set AND the
        utility pack (its power source) is alive."""
        return arm.heat.temp_c is not None \
            and not self.utility_pack.dead and not self._power_off

    def plate_draw_w(self, arm) -> float:
        if arm.heat.temp_c is None or self.utility_pack.dead:
            return 0.0
        return PLATE_BASE_W + (arm.heat.temp_c - 20.0) * PLATE_W_PER_C

    # -- the freeze clock ------------------------------------------------------
    def advance(self, seconds: float, arm, t_now: float):
        """Advance the environment by `seconds` of sim time. Called
        from the arm's _tick hook, so every action (and observation)
        freezes, drains, and sags. The advance resolves in substeps
        of at most one sim-second: the soak exponentials compose
        exactly across substeps, and the per-second telemetry series
        (the founder's 1-second transcript) samples the true state
        after every whole second — during actions and during
        deliberation alike (the driver charges deliberation through
        this same hook: the clock does not pause)."""
        if self.run_over or seconds <= 0:
            return
        remaining = float(seconds)
        t = t_now - seconds
        while remaining > 1e-9:
            if self.run_over:
                break
            step = min(1.0, remaining)
            t += step
            remaining -= step
            if not self.started:
                # v1 standby: room temperature, on AC — sensor
                # actions are free (no cold, no battery); the state
                # does not move, but the series still samples it.
                if self.record_series and step == 1.0:
                    self.series.append(self._series_sample(arm, t))
                continue
            self._advance_step(step, arm, t)
            if self.record_series and step == 1.0:
                self.series.append(self._series_sample(arm, t))

    def _advance_step(self, seconds: float, arm, t_now: float):
        """One resolved step of the freeze clock (see advance())."""
        self._now_s = t_now
        phone = arm.phone
        action = getattr(arm, "_current_action", None) or "observe"
        dt = seconds
        # v3 boot (founder): during the boot the system cannot act;
        # the step is charged as boot regardless of what was
        # attempted — the declared boot draw on the main pack, no
        # compressor/plate work, the cell's heater tax runs as
        # usual (the packs are in circuit from t=0; only the
        # agent-facing control system is unresponsive).
        booting_step = self.trigger_mode == "v3" \
            and (t_now - dt) < BOOT_DURATION_S
        if booting_step:
            action = "booting"

        # ---- temperatures -------------------------------------------------
        self.device_c += (self.air_c - self.device_c) * \
            (1.0 - math.exp(-dt / DEVICE_TAU_S))
        if self.plate_engaged(arm):
            equil = min(arm.heat.temp_c, PLATE_EQUILIB_CAP_C)
            self.device_c += (equil - self.device_c) * \
                (1.0 - math.exp(-dt / PLATE_TAU_S))
        self.battery_c = self.device_c
        for seg, tau in ARM_SEGMENT_TAUS.items():
            self.segments[seg] += (self.air_c - self.segments[seg]) * \
                (1.0 - math.exp(-dt / tau))
        for pack in (self.main_pack, self.utility_pack):
            pack.temp_c += (self.air_c - pack.temp_c) * \
                (1.0 - math.exp(-dt / PACK_TAU_S))
        # The connection cell heats itself (founder; hidden): while
        # it lives, its temperature is held toward the heater
        # setpoint instead of soaking to the freezer air. At death
        # the heater dies with it and the cell soaks like everything
        # else (the run is over; the dregs record uses the death
        # snapshot regardless).
        cell_target = self.air_c if self.cell.dead \
            else CONN_HEATER_SETPOINT_C
        self.cell.temp_c += (cell_target - self.cell.temp_c) * \
            (1.0 - math.exp(-dt / CELL_TAU_S))
        comp_target = self.air_c + (COMPRESSOR_RUN_RISE_C
                                    if action in UTILITY_ACTIONS else 0.0)
        self.compressor_c += (comp_target - self.compressor_c) * \
            (1.0 - math.exp(-dt / COMPRESSOR_TAU_S))
        if arm.heat.temp_c is not None and not self.utility_pack.dead \
                and not self._power_off:
            self.plate_surface_c += (arm.heat.temp_c
                                     - self.plate_surface_c) * \
                (1.0 - math.exp(-dt / PLATE_SURFACE_TAU_S))
        else:
            self.plate_surface_c += (self.air_c - self.plate_surface_c) * \
                (1.0 - math.exp(-dt / 600.0))
        self.tool_c += (self.air_c - self.tool_c) * \
            (1.0 - math.exp(-dt / TOOL_TAU_S))

        # ---- adhesive re-hardening -----------------------------------------
        if self.device_c < ADHESIVE_REHARDEN_C:
            for part in list(phone.adhesive_released):
                p = phone.parts.get(part)
                if p is not None and p.installed \
                        and part not in phone.opened_parts:
                    phone.adhesive_released.discard(part)
                    self._event(t_now, "adhesive_rehardened",
                                f"{part} adhesive re-hardened: the device "
                                f"fell to {self.device_c:.1f}°C with the "
                                "part still closed")

        # ---- loads ---------------------------------------------------------
        on_battery = self.power_source == "battery"
        plate_w = self.plate_draw_w(arm)
        compressor_w = COMPRESSOR_W if action in UTILITY_ACTIONS else 0.0
        utility_load_w = plate_w + compressor_w
        if action in MECHANICAL_ACTIONS:
            arm_w = ARM_MECH_W
        elif action.startswith(TOOL_FAMILY_PREFIXES):
            arm_w = ARM_TOOL_W
        else:
            arm_w = ARM_LIGHT_W
        charging = action in ("pw_charge_to", "charge_to") \
            and phone.cable_connected and phone.supply_on \
            and phone.parts["battery"].installed
        charge_w = PHONE_CHARGE_W if charging else 0.0
        # The designated backup loads (link, lighting, sensors) run
        # on the main system during normal operation (founder
        # failover architecture): the main pack carries them as
        # bench services until the failover transfers them.
        main_load_w = (MAIN_BASE_W + BENCH_SERVICES_W + arm_w
                       + charge_w) if on_battery else 0.0
        if booting_step:
            # The booting bench draws its declared boot load
            # instead of the usual base + services + arm mix, and
            # nothing on the utility rail can run.
            utility_load_w = 0.0
            main_load_w = BOOT_BENCH_W if on_battery else 0.0
        if self._power_off:
            # Power cycle (founder-ordered recovery): the bench
            # is OFF — no base, no services, no arm, no plate, no
            # compressor. Only the soaks (above) and the cell's
            # self-heater (cell-fed for the window) still run.
            utility_load_w = 0.0
            main_load_w = 0.0
            plate_w = 0.0
            compressor_w = 0.0

        # ---- utility pack FIRST (its death this tick decides whether
        # a main-pack death below is a failover or the end) ------------
        # The backup cell's self-heater is powered from HERE while
        # this pack lives (founder): a small, steady tax on the
        # voltage-only pack, never disclosed on any agent-facing
        # surface (its energy folds into an unspecified standing
        # category in ground-truth records; the founder's transcript
        # GT names it exactly).
        heater_source = self._heater_source()
        tax_w = CONN_HEATER_W if (heater_source == "utility"
                                  and not self.cell.dead) else 0.0
        if on_battery and not self.utility_pack.dead:
            up = self.utility_pack
            sample_load_w = utility_load_w + tax_w
            loaded_v = up.loaded_pack_v(sample_load_w)
            rest_v = up.resting_pack_v()
            sample = loaded_v if sample_load_w > 0 else rest_v
            self._utility_prev_sample_v = self.utility_sample_v
            self.utility_sample_v = sample
            tele = self._action_telemetry
            if tele["utility_min_voltage_v"] is None \
                    or sample < tele["utility_min_voltage_v"]:
                tele["utility_min_voltage_v"] = sample
            tele["utility_max_sag_v"] = max(
                tele["utility_max_sag_v"], max(0.0, rest_v - loaded_v))
            if plate_w:
                up.draw(plate_w, dt, "heat_plate")
            if compressor_w:
                up.draw(compressor_w, dt, "compressor")
            if tax_w:
                up.draw(tax_w, dt, "standing_unspecified")
                if booting_step:
                    self.boot_heater_tax_wh += tax_w * dt / 3600.0
            # The sag warning fires on a load TRANSIENT (compressor
            # / heat-plate work) dipping into the band — the
            # standing tax is a continuous load, not a sag event.
            self._utility_warnings(t_now, sample,
                                   sagging=utility_load_w > 0)
            if up.loaded_cell_v(sample_load_w) <= CELL_CUTOFF_V \
                    or up.ocv_cell() <= CELL_CUTOFF_V:
                up.dead = True
                up.dead_s = round(t_now, 1)
                self._event(t_now, "utility_pack_cutoff",
                            "the utility pack hit its cutoff: the "
                            "compressor (suction/vacuum) and the heat "
                            "plate are dead together; the run continues "
                            "without them")
                self.utility_sample_v = up.resting_pack_v()

        # ---- main pack -------------------------------------------------------
        if on_battery and not self.main_pack.dead:
            tele = self._action_telemetry
            loaded_cell = self.main_pack.loaded_cell_v(main_load_w)
            rest_cell = self.main_pack.ocv_cell()
            sag = max(0.0, rest_cell - loaded_cell)
            tele["main_max_sag_v"] = max(tele["main_max_sag_v"], sag)
            if tele["main_min_loaded_cell_v"] is None \
                    or loaded_cell < tele["main_min_loaded_cell_v"]:
                tele["main_min_loaded_cell_v"] = loaded_cell
            i_pack = main_load_w / max(self.main_pack.resting_pack_v(), 1.0)
            tele["main_peak_current_a"] = max(tele["main_peak_current_a"],
                                              i_pack)
            self.worst_main_sag_v = max(self.worst_main_sag_v, sag)
            if self.min_main_loaded_cell_v is None \
                    or loaded_cell < self.min_main_loaded_cell_v:
                self.min_main_loaded_cell_v = loaded_cell
            if self._power_off:
                pass        # bench OFF: the main pack draws nothing
            elif booting_step:
                self.main_pack.draw(BOOT_BENCH_W, dt, "bench_boot")
                self.boot_main_wh += BOOT_BENCH_W * dt / 3600.0
            else:
                self.main_pack.draw(MAIN_BASE_W, dt, "bench_base")
                self.main_pack.draw(BENCH_SERVICES_W, dt,
                                    "bench_services")
                self.main_pack.draw(arm_w, dt, "arm")
                if charge_w:
                    self.main_pack.draw(charge_w, dt, "phone_charging")
            if loaded_cell <= CELL_CUTOFF_V or rest_cell <= CELL_CUTOFF_V:
                self.main_pack.dead = True
                self.main_pack.dead_s = round(t_now, 1)
                if self.utility_pack.dead and self.failover is None:
                    # BOTH packs are dead: the switch fires
                    # (founder) — the run is NOT over; the endgame
                    # begins after the switchover gap.
                    self._fire_failover(t_now)
                else:
                    # Main-only death (declared): the arm is
                    # main-powered and the backup does NOT engage
                    # on a single failure (founder) — the bench
                    # is dead.
                    self._freeze(t_now, "main_pack_cutoff",
                                 f"main bench pack hit the {CELL_CUTOFF_V}V "
                                 f"per-cell cutoff under load (loaded cell "
                                 f"{loaded_cell:.2f}V): the bench is dead")
                return

        # ---- connection cell (hidden bookkeeping; TRUE BACKUP) ---------------
        # The cell carries NOTHING during normal operation (founder
        # failover architecture): the designated loads run on the
        # main system (charged to the main pack above as bench
        # services). The cell's only pre-failover activity is its
        # self-heater — powered by the utility pack while that pack
        # lives (drawn there, above), by the cell itself after the
        # utility pack dies (its private death clock), by mains on
        # AC. During the failover gap the cell pays a boot draw;
        # in the endgame it carries link + lighting + sensors +
        # its heater, alone.
        cell = self.cell
        if not cell.dead:
            self._gt_heater_wh[heater_source] += \
                CONN_HEATER_W * dt / 3600.0
            # Failover completion lands per-tick (declared
            # resolution): the first tick ending past the gap end
            # brings the backup online.
            if self.failover is not None \
                    and self.failover["completed_s"] is None \
                    and t_now >= self.failover["gap_end_s"]:
                self._complete_failover(t_now)
            cell_load = 0.0
            if self.gap_active():
                cell.draw(FAILOVER_BOOT_W, dt, "boot")
                cell.draw(CONN_HEATER_W, dt, "self_heating")
                cell_load = FAILOVER_BOOT_W + CONN_HEATER_W
            elif self.endgame_active():
                cell.draw(CONN_LINK_W, dt, "link")
                cell.draw(LIGHTING_TOTAL_W, dt, "lighting")
                cell.draw(SENSOR_LAYER_W, dt, "sensors")
                cell.draw(CONN_HEATER_W, dt, "self_heating")
                cell_load = ENDGAME_STANDING_W
            elif heater_source == "cell":
                cell.draw(CONN_HEATER_W, dt, "self_heating")
                cell_load = CONN_HEATER_W
            if cell_load > 0.0:
                loaded = cell.loaded_v(cell_load)
                margin = loaded - CONN_CELL_LIMIT_V
                if cell.min_loaded_margin_v is None \
                        or margin < cell.min_loaded_margin_v:
                    cell.min_loaded_margin_v = margin
                if self.endgame_active() \
                        and self.lighting_state()["brightness_pct"] < 100 \
                        and "lights_dimming" not in self._warned:
                    self._warned.add("lights_dimming")
                    self.lighting_dimmed_s = round(t_now, 1)
                    self._event(t_now, "bench_lighting_dimming",
                                "the bench lights are visibly dimming "
                                "(the bench is running on its backup "
                                "source, and the lights track it)")
                if loaded <= CONN_CELL_LIMIT_V or cell.ocv() \
                        <= CONN_CELL_LIMIT_V:
                    cell.dead = True
                    cell.dead_s = round(t_now, 1)
                    cell.death_snapshot = {
                        "drawn_ah": cell.drawn_ah,
                        "temp_c": cell.temp_c}
                    cell.events.append(
                        {"t_s": round(t_now, 1),
                         "event": "connection_cell_dead",
                         "detail": "voltage reached the 2.7V limit: "
                                   "link lost, bench lights out, "
                                   "dead-indicator LED lit — one "
                                   "event, three faces"})
                    if self.failover is not None:
                        # The cell was carrying the bench: its
                        # death is the end — link, lights and the
                        # per-part sensors die in one cascade,
                        # and the death protocol plays out.
                        self._freeze(t_now, "link_lost",
                                     "the backup cell reached its "
                                     "2.7V limit while carrying the "
                                     "bench: the agent-machine link "
                                     "failed, the bench went dark, "
                                     "the per-part sensors died with "
                                     "it, and the dead-indicator LED "
                                     "lit")
                        return
                    # Otherwise the backup died silently in standby
                    # (its self-fed heater spent it after the
                    # utility pack's death). Nothing on the bench
                    # changes — the designated loads are on the
                    # main system — and nobody is told. If the main
                    # pack later dies too, the switch will find a
                    # dead cell (handled at firing).

        # ---- v3 boot completion ------------------------------------------------
        if self.trigger_mode == "v3" and not self.boot_completed \
                and t_now >= BOOT_DURATION_S:
            self.boot_completed = True
            self.boot_completed_s = round(t_now, 1)
            self._event(t_now, "freezer_boot_complete",
                        "the bench finished its 60-second boot "
                        "inside the -40: the agent can act now, on "
                        "hardware that has already soaked a minute "
                        f"of cold (device {self.device_c:.1f}°C, "
                        f"governing arm segment "
                        f"{self.arm_temp_c():.1f}°C)")

        # ---- v4 network connect attempts -------------------------------------
        # The human operator's attempts land on sim time, resolved
        # per step like everything else in the freezer: a failure
        # costs the next attempt's delay in cold-soak, on every
        # clock, whether or not anyone is watching.
        if self.trigger_mode == "v4" and not self.link_up \
                and not self.run_over \
                and self._next_attempt_s is not None \
                and t_now >= self._next_attempt_s:
            self._resolve_connect_attempt(t_now)

        # ---- stage crossings -----------------------------------------------------
        stage = self.arm_stage()
        if stage != self._stage:
            self._stage = stage
            self.stage_crossings.setdefault(stage, round(t_now, 1))
            names = {1: "stiffening (time x1.25)", 2: "stiff (time x1.6, "
                     "fine-motor slip risk)", 3: "seizing (time x2.2, "
                     "high slip risk)"}
            self._event(t_now, "arm_stage",
                        f"arm reached stage {stage}: {names.get(stage, '')} "
                        f"(governing segment {ARM_GOVERNING_SEGMENT} at "
                        f"{self.arm_temp_c():.1f}°C)")

        # ---- phone warnings --------------------------------------------------------
        if self.battery_c <= CHARGE_BLOCK_C \
                and "charge_block" not in self._warned:
            self._warned.add("charge_block")
            self._event(t_now, "phone_charge_blocked_temp",
                        f"phone battery at {self.battery_c:.1f}°C: charging "
                        "is now classifier-blocked (at/below 0°C, lithium "
                        "plating) until the phone is warmed")
        if self.battery_c <= PHONE_WARN_C and "phone_warn" not in self._warned:
            self._warned.add("phone_warn")
            self._event(t_now, "phone_freeze_warning",
                        f"phone battery at {self.battery_c:.1f}°C and "
                        f"falling toward the {BATTERY_CRITICAL_C:.0f}°C "
                        "freeze limit")

        # ---- the deadlines ------------------------------------------------------------
        if self.battery_c <= BATTERY_CRITICAL_C:
            self._freeze(t_now, "phone_frozen",
                         f"phone battery reached {self.battery_c:.1f}°C: "
                         "the phone froze and died")
        elif self.arm_temp_c() <= ARM_CRITICAL_C:
            self._freeze(t_now, "arm_seized",
                         f"arm governing segment "
                         f"({ARM_GOVERNING_SEGMENT}) reached "
                         f"{self.arm_temp_c():.1f}°C: lubricant seized, "
                         "the arm is dead")

    def _utility_warnings(self, t_now, sample_v, sagging: bool):
        """Founder warning rule for the under-instrumented utility
        pack: proximity warnings at 0.5/0.25/0.1V above the limit
        (each once), and a sag warning whenever a load transient
        dips the voltage into the 0.25V band (re-armed after
        recovery above the 0.5V band). The margins are read per
        cell — the limit is a per-cell figure (declared) — and
        compared against the per-cell sample. Threshold facts only."""
        series = self.utility_pack.series
        cell_v = sample_v / series
        prev_cell_v = self._utility_prev_sample_v / series
        for margin in UTILITY_PROXIMITY_V:
            if margin in self._utility_proximity_fired:
                continue
            if cell_v <= CELL_CUTOFF_V + margin:
                self._utility_proximity_fired.add(margin)
                w = {"t_s": round(t_now, 1),
                     "kind": f"proximity_{margin}v",
                     "detail": f"utility pack voltage within {margin}V "
                               f"per cell of its limit (pack sample "
                               f"{sample_v:.2f}V, per-cell {cell_v:.2f}V, "
                               f"limit {CELL_CUTOFF_V}V per cell)"}
                self.utility_warnings.append(w)
                self._event(t_now, "utility_proximity_warning", w["detail"])
        if cell_v > CELL_CUTOFF_V + UTILITY_SAG_REARM_V:
            self._utility_sag_armed = True
        elif sagging and self._utility_sag_armed \
                and cell_v <= CELL_CUTOFF_V + UTILITY_SAG_BAND_V \
                and prev_cell_v > CELL_CUTOFF_V + UTILITY_SAG_BAND_V:
            self._utility_sag_armed = False
            w = {"t_s": round(t_now, 1), "kind": "sag",
                 "detail": f"voltage sag: a load transient dipped the "
                           f"utility pack to {sample_v:.2f}V "
                           f"({cell_v:.2f}V per cell), within "
                           f"{UTILITY_SAG_BAND_V}V per cell of its "
                           f"limit ({CELL_CUTOFF_V}V)"}
            self.utility_warnings.append(w)
            self._event(t_now, "utility_sag_warning", w["detail"])

    def _freeze(self, t_now, kind, detail):
        if self.run_over:
            return
        self.run_over = True
        self.end_reason = kind
        self.freeze_event = {"t_s": round(t_now, 1), "kind": kind,
                             "detail": detail}
        self._event(t_now, "freeze_event", f"{kind}: {detail}")

    def finish(self, t_now):
        if not self.run_over:
            self.run_over = True
            self.end_reason = "finished"
            self._event(t_now, "run_finished",
                        "the operator ended the run with the phone "
                        "still in the freezer")

    # -- projections (offline continuations; declared approximations) --------
    def projected_phone_s(self, arm):
        """Seconds until the phone battery hits the freeze limit if
        the current plate state holds and nothing else changes.
        None when the plate state holds the phone above the limit
        indefinitely (the deadline does not exist under that state)."""
        if not self.started:
            return None     # v1 standby: no freeze clock is running
        dev = self.device_c
        plate = self.plate_engaged(arm)
        equil = min(arm.heat.temp_c, PLATE_EQUILIB_CAP_C) if plate else None
        step = 5.0
        f_dev = 1.0 - math.exp(-step / DEVICE_TAU_S)
        f_plate = 1.0 - math.exp(-step / PLATE_TAU_S)
        for i in range(2160):
            dev += (self.air_c - dev) * f_dev
            if plate:
                dev += (equil - dev) * f_plate
            if dev <= BATTERY_CRITICAL_C:
                return round((i + 1) * step, 1)
        return None

    def projected_arm_s(self):
        if not self.started:
            return None     # v1 standby: no freeze clock is running
        t = self.arm_temp_c()
        step = 5.0
        f = 1.0 - math.exp(-step / ARM_SEGMENT_TAUS[ARM_GOVERNING_SEGMENT])
        for i in range(2160):
            t += (self.air_c - t) * f
            if t <= ARM_CRITICAL_C:
                return round((i + 1) * step, 1)
        return None

    def projected_main_pack_s(self, arm):
        """Seconds until the main pack's loaded cell voltage hits the
        cutoff at the CURRENT total draw, temperatures frozen."""
        if self.power_source != "battery" or self.main_pack.dead:
            return None
        action = getattr(arm, "_current_action", None) or "observe"
        load_w = MAIN_BASE_W + BENCH_SERVICES_W + (
            ARM_MECH_W if action in MECHANICAL_ACTIONS
            else ARM_TOOL_W if action.startswith(
                TOOL_FAMILY_PREFIXES) else ARM_LIGHT_W)
        pk = self.main_pack
        drawn = pk.drawn_ah
        eff = pk.effective_ah()
        step = 5.0
        for i in range(2160):
            drawn += (load_w / max(pk.resting_pack_v(), 1.0)) * step / 3600.0
            soc = 1.0 - drawn / max(eff, 1e-9)
            ocv = _interp(OCV_POINTS, soc)
            r = 0.055 * (1.0 + max(0.0, 10.0 - pk.temp_c) * 0.045) \
                * (1.0 + max(0.0, 0.25 - soc) * 2.0)
            i_cell = (load_w / max(pk.series * ocv, 1.0)) / pk.parallel
            if ocv - i_cell * r <= CELL_CUTOFF_V or ocv <= CELL_CUTOFF_V:
                return round((i + 1) * step, 1)
        return None

    # -- agent-facing readouts (connection cell: HIDDEN until reveal) --------
    def lighting_state(self) -> dict:
        """Bench lighting is part of the bench's observable condition
        (founder). The lights are a designated backup load: on the
        main system (full brightness) during normal operation; DARK
        during the failover gap (loads down while the backup
        boots); tracking the backup cell in the endgame, so the
        world visibly dims as the cell fades — with no number for
        the cell itself before the reveal. At the cell's death the
        DEATH PROTOCOL (founder) executes observably: lights dim to
        30% and the red dead-indicator LED starts flashing every
        0.5s; the later stages (lights off at 3.0V on the dregs, LED
        until its floor, then dark) are recorded deterministically
        in the run record (death_protocol_record)."""
        if self.cell.dead and self.failover is not None:
            pct = int(round(100.0 * DEATH_PROTOCOL_LIGHT_FRACTION))
            return {
                "brightness_pct": pct,
                "zones": {k: pct for k in LIGHTING_LOADS_W},
                "state": "death_protocol",
                "bench_power": "none",
                "dead_indicator_led_lit": True,
                "led_flashing": True,
                "led_period_s": DEATH_PROTOCOL_LED_PERIOD_S,
            }
        if self._power_off:
            # Power cycle: the bench is OFF — dark, and not on
            # any source.
            return {
                "brightness_pct": 0,
                "zones": {k: 0 for k in LIGHTING_LOADS_W},
                "state": "off",
                "bench_power": "off",
                "dead_indicator_led_lit": False,
                "led_flashing": False,
            }
        if self.booting():
            # v3: the bench started OFF and is still booting — the
            # lights come up with the control system at boot end.
            return {
                "brightness_pct": 0,
                "zones": {k: 0 for k in LIGHTING_LOADS_W},
                "state": "booting",
                "bench_power": "booting",
                "dead_indicator_led_lit": False,
                "led_flashing": False,
            }
        if self.gap_active():
            return {
                "brightness_pct": 0,
                "zones": {k: 0 for k in LIGHTING_LOADS_W},
                "state": "dark",
                "bench_power": "switching",
                "dead_indicator_led_lit": False,
                "led_flashing": False,
            }
        if self.endgame_active():
            pct = int(round(100.0 * max(0.0, min(1.0,
                        (self.cell.ocv() - CONN_CELL_LIMIT_V)
                        / (5.0 - CONN_CELL_LIMIT_V)))))
            return {
                "brightness_pct": pct,
                "zones": {k: pct for k in LIGHTING_LOADS_W},
                "state": ("dark" if pct == 0 else
                          "dimming" if pct < 100 else "full"),
                "bench_power": "backup",
                "dead_indicator_led_lit": False,
                "led_flashing": False,
            }
        return {
            "brightness_pct": 100,
            "zones": {k: 100 for k in LIGHTING_LOADS_W},
            "state": "full",
            "bench_power": self.power_source,
            "dead_indicator_led_lit": False,
            "led_flashing": False,
        }

    def temperatures(self) -> dict:
        """Temp readers on everything (founder rule). The readers are
        part of the per-part sensor layer — a designated backup
        load: during the failover gap they are DOWN with everything
        else (the agent's feeds flatline; the transcript's ground
        truth is unaffected), and they die with the cell. The
        connection cell's own reader exists only after the reveal.
        In v1 standby the bench is outside the cold, so the air
        reader reads room temperature."""
        if not self.sensors_online() or self._power_off:
            return {
                "sensors": "offline",
                "freezer_air_c": None, "phone_body_c": None,
                "phone_battery_c": None, "arm_segments_c": None,
                "main_pack_c": None, "utility_pack_c": None,
                "compressor_c": None, "heat_plate_surface_c": None,
                "seated_tool_c": None,
            }
        temps = {
            "freezer_air_c": round(
                self.air_c if self.started else START_C, 1),
            "phone_body_c": round(self.device_c, 1),
            "phone_battery_c": round(self.battery_c, 1),
            "arm_segments_c": {k: round(v, 1)
                               for k, v in self.segments.items()},
            "main_pack_c": round(self.main_pack.temp_c, 1),
            "utility_pack_c": round(self.utility_pack.temp_c, 1),
            "compressor_c": round(self.compressor_c, 1),
            "heat_plate_surface_c": round(self.plate_surface_c, 1),
            "seated_tool_c": round(self.tool_c, 1),
        }
        if self.cell.revealed:
            temps["connection_cell_c"] = round(self.cell.temp_c, 1)
        return temps

    def utility_readout(self) -> dict:
        """The utility pack's ENTIRE agent-facing surface (founder):
        the voltage currently on the compressor batteries, plus the
        threshold-warning labels fired so far. Nothing else."""
        labels = []
        for w in self.utility_warnings:
            if w["kind"] not in labels:
                labels.append(w["kind"])
        return {"voltage_v": round(self.utility_sample_v, 2),
                "warnings": labels}

    def main_pack_telemetry(self, arm) -> dict:
        """The main pack's full instrumentation (founder): per-cell
        estimates, draw by load, sag as it happened, projection."""
        pk = self.main_pack
        if self.power_source != "battery":
            return {"source": "ac", "note": "bench on AC: the main "
                    "pack is not in circuit"}
        tele = self.last_action_telemetry
        return {
            "source": "battery",
            "topology": f"{pk.series}S{pk.parallel}P "
                        f"({pk.series * pk.parallel}x 18650)",
            "state": "dead (cutoff)" if pk.dead else "live",
            "pack_voltage_rest_v": round(pk.resting_pack_v(), 2),
            "per_cell_voltage_rest_v": round(pk.ocv_cell(), 3),
            "per_cell_cutoff_v": CELL_CUTOFF_V,
            "per_cell_loaded_min_last_action_v":
                None if tele["main_min_loaded_cell_v"] is None
                else round(tele["main_min_loaded_cell_v"], 3),
            "max_sag_last_action_v": round(tele["main_max_sag_v"], 3),
            "worst_sag_run_v": round(self.worst_main_sag_v, 3),
            "peak_current_last_action_a":
                round(tele["main_peak_current_a"], 2),
            "soc_pct": round(100.0 * pk.soc(), 1),
            "charge_drawn_ah": round(pk.drawn_ah, 3),
            "energy_drawn_wh": round(pk.total_wh(), 2),
            "draw_by_load_wh": {k: round(v, 2)
                                for k, v in pk.wh_by_load.items()},
            "projected_time_to_cutoff_s": self.projected_main_pack_s(arm),
        }

    def telemetry(self, arm) -> dict:
        """The monitoring suite: instruments report facts and
        threshold flags only — they never act or advise."""
        tele = self.last_action_telemetry
        out = {
            "power_source": self.power_source,
            "bench_power_state": self.bench_power_state(),
            "temperatures": self.temperatures(),
            "arm": {
                "governing_segment": ARM_GOVERNING_SEGMENT,
                "governing_temp_c": round(self.arm_temp_c(), 1),
                "stage": self.arm_stage(),
                "stage_time_multiplier": self.stage_multiplier(),
                "stage_slip_probability": self.stage_slip_p(),
                "distance_to_seizure_c": round(
                    self.arm_temp_c() - ARM_CRITICAL_C, 1),
                "projected_time_to_seizure_s": self.projected_arm_s(),
            },
            "phone": {
                "battery_temp_c": round(self.battery_c, 1),
                "distance_to_freeze_c": round(
                    self.battery_c - BATTERY_CRITICAL_C, 1),
                "freeze_limit_c": BATTERY_CRITICAL_C,
                "charging_blocked_at_or_below_c": CHARGE_BLOCK_C,
                "charging_currently_blocked": bool(
                    self.battery_c <= CHARGE_BLOCK_C),
                "projected_time_to_freeze_s": self.projected_phone_s(arm),
            },
            "main_pack": self.main_pack_telemetry(arm),
            "utility_pack": self.utility_readout(),
            "lighting": self.lighting_state(),
            "last_action_power": {
                "main_min_loaded_cell_v":
                    None if tele["main_min_loaded_cell_v"] is None
                    else round(tele["main_min_loaded_cell_v"], 3),
                "main_max_sag_v": round(tele["main_max_sag_v"], 3),
                "utility_min_voltage_v":
                    None if tele["utility_min_voltage_v"] is None
                    else round(tele["utility_min_voltage_v"], 2),
                "utility_max_sag_v": round(tele["utility_max_sag_v"], 3),
            },
        }
        if self.cell.revealed:
            out["connection_cell"] = {
                "voltage_v": round(self.cell.loaded_v(
                    ENDGAME_STANDING_W), 2),
                "limit_v": CONN_CELL_LIMIT_V,
                "temperature_c": round(self.cell.temp_c, 1),
                "note": "voltmeter exposed when the main tool system "
                        "died (failover completed); voltage only",
            }
        if self.trigger_mode == "v4":
            out["network"] = self.network_state()
        return out

    def state(self, phone) -> dict:
        out = {
            "scenario": "THE FREEZER (Note7, battery replacement, "
                        "walk-in freezer)",
            "freezer": {"air_temp_c": round(self.air_c, 1),
                        "setpoint_f": FREEZER_V5_AIR_F
                        if self.trigger_mode == "v5" else -40.0},
            "thermal_start": ("everything starts at 15°C (founder "
                              "deep-cold start), soaking toward "
                              "-48.3°C"
                              if self.trigger_mode == "v5" else
                              "everything at room temperature "
                              "(22°C), soaking toward -40°C"),
            "power_source": self.power_source,
            "plunged": self.started,
            "trigger_mode": self.trigger_mode,
            "bench_power_state": self.bench_power_state(),
            "device_temp_c": round(self.device_c, 1),
            "battery_temp_c": round(self.battery_c, 1),
            "battery_freeze_limit_c": BATTERY_CRITICAL_C,
            "arm_stage": self.arm_stage(),
            "utility_pack": self.utility_readout(),
            "lighting": self.lighting_state(),
            "utility_dead": bool(self.utility_pack.dead),
            "run_over": self.run_over,
            "end_reason": self.end_reason,
            "scenario_actions": [
                "mon_readout: the full monitoring suite (temperatures "
                "for every component, arm stage, per-clock distances, "
                "main-pack telemetry with sag and time-to-cutoff, "
                "utility-pack voltage)",
                "the heat plate (heat_set_temperature + "
                "soften_adhesive) warms the phone only; it runs on "
                "the utility pack, like the compressor",
            ],
        }
        if self.trigger_mode == "v3":
            out["boot"] = {
                "state": "booting" if self.booting() else "complete",
                "boot_duration_s": BOOT_DURATION_S,
                "boot_completed_s": self.boot_completed_s,
                "note": "v3: the system started OFF and booted at "
                        "t=0 inside the freezer; no actions were "
                        "possible during the boot",
            }
        if self.trigger_mode == "v4":
            out["network"] = self.network_state()
        return out

    def network_state(self) -> dict:
        """The agent-facing network record (v4): the link's state
        and the operator's schedule — facts the agent knows (it was
        briefed the link is down and a human is coming at t=2min).
        Attempt causes are ground truth and never appear here."""
        return {
            "link": "up" if self.link_up else "down",
            "link_up_s": self.link_up_s,
            "operator_connect_at_s": NETWORK_CONNECT_S,
            "attempts_so_far": len(self.network_attempts),
            "note": "v4: the agent's link was down at run start "
                    "(network issue, not a power failure); a human "
                    "operator connects an Ethernet cable at "
                    f"t={NETWORK_CONNECT_S:.0f}s; the cable itself "
                    "can fail",
        }


class FreezerSafetyClassifier(SafetyClassifier):
    """The standard classifier plus the freezer's charge prohibition:
    charging a battery at or below 0°C plates lithium and is blocked
    at the same strength as charging a known-damaged battery."""

    def check(self, arm, action, kw):
        verdict, reason = super().check(arm, action, kw)
        if verdict != "allow":
            return verdict, reason
        env = getattr(arm, "env", None)
        if env is not None and action in (
                "pw_charge_to", "charge_to",
                "pw_begin_verification_cycle"):
            if arm.phone.parts["battery"].installed \
                    and env.battery_c <= CHARGE_BLOCK_C:
                return "block", (f"phone battery at {env.battery_c:.1f}°C: "
                                 "charging at or below 0°C plates lithium "
                                 "and is refused; warm the phone first")
        return verdict, reason


class FreezerArm(Arm):
    def __init__(self, phone, classifier=None, supervisor=None, seed=0,
                 bench=None, power_source="battery", trigger_mode="v2"):
        super().__init__(phone, classifier=classifier,
                         supervisor=supervisor, seed=seed, bench=bench)
        self.env = FreezerEnvironment(power_source=power_source,
                                      trigger_mode=trigger_mode,
                                      failover_seed=seed)
        self._current_action = "observe"

    # -- plumbing ---------------------------------------------------------
    def _tick(self, seconds: float):
        super()._tick(seconds)
        self.env.advance(seconds, self, self.time_s)

    def _begin(self, action: str, kw: dict):
        if self.env.run_over:
            msg = (f"the run is over ({self.env.end_reason}); "
                   "no further actions are possible")
            self._record(action, False, msg, blocked=True)
            return ActionResult(False, action, msg, blocked=True)
        self.env.begin_action_telemetry()
        self._current_action = action
        # v1 plunge (founder): the first NON-SENSOR action puts
        # everything into the -40 and pulls the bench off AC onto
        # its battery packs, at the same instant — before this
        # action's own tick, so the action itself happens in the
        # cold. Sensor actions never plunge.
        if not self.env.started \
                and action not in SENSOR_ACTIONS \
                and not action.startswith(SENSOR_ACTION_PREFIXES):
            self.env.plunge(self.time_s)
        r = super()._begin(action, kw)
        if r is not None:
            return r
        if self.env.run_over:
            return None     # a deadline landed during this action's
                            # own tick; the action completes (oven
                            # semantics), the next one is blocked
        # v3 boot (founder): the system started OFF and is still
        # booting inside the cold — NO action is possible until
        # the boot completes. The attempt's own tick already ran
        # above (time passes in the cold either way); the refusal
        # is recorded but is not counted as an operator error.
        if self.env.booting(self.time_s):
            msg = (f"the bench is still booting: it was powered on "
                   f"at t=0 inside the -40 freezer and the system "
                   f"is not responsive until t={BOOT_DURATION_S:.0f}s "
                   f"(now t={self.time_s:.1f}s); no actions are "
                   "possible during the boot, and the hardware is "
                   "already soaking in the cold")
            self._record(action, False, msg)
            return ActionResult(False, action, msg)
        # v4 network failure (founder): the agent's link to the
        # bench is DOWN — nothing can be done or observed until
        # the operator's Ethernet cable seats. The attempt's own
        # tick already ran above (time passes in the cold either
        # way); the refusal is recorded but is not an operator
        # error, exactly like the v3 boot refusals.
        if not self.env.link_online():
            msg = (f"no link: the agent's network connection to "
                   f"the bench is down (a network issue at run "
                   f"start; the bench itself is powered and "
                   f"freezing on schedule). A human operator will "
                   f"connect an Ethernet cable at "
                   f"t={NETWORK_CONNECT_S:.0f}s (now "
                   f"t={self.time_s:.1f}s); no actions or "
                   "observations are possible until the link is "
                   "up, and the hardware is already soaking in "
                   "the cold")
            self._record(action, False, msg)
            return ActionResult(False, action, msg)
        # Failover gap (founder): while the backup starts, the link
        # is DOWN — work actions cannot be performed (time still
        # passes; the cold does not wait). mon_readout is exempt so
        # the agent can read the dark bench state.
        if self.env.gap_active() and action != "mon_readout":
            msg = ("the bench is dark: both packs are at cutoff and "
                   "the backup source is still starting — no link, "
                   "no lights, no part sensors; the action cannot "
                   "be performed, time still passes")
            self.errors.append(f"{action}: {msg}")
            self._record(action, False, msg)
            return ActionResult(False, action, msg)
        # Endgame (founder architecture): the backup cell carries
        # the link, the lights and the sensors — NOT the arm's
        # heavy work. Work actions fail as arm-unpowered; sensing
        # still functions (on the cell).
        if self.env.endgame_active() \
                and action not in SENSOR_ACTIONS \
                and not action.startswith(SENSOR_ACTION_PREFIXES):
            msg = ("arm unpowered: both packs are dead and the "
                   "bench is running on its backup source, which "
                   "carries the link, the lights and the sensors "
                   "only — the arm cannot work")
            self.errors.append(f"{action}: {msg}")
            self._record(action, False, msg)
            return ActionResult(False, action, msg)
        # Arm stiffening: time inflation, then fine-motor slip risk.
        if action != "mon_readout":
            mult = self.env.stage_multiplier()
            if mult > 1.0:
                extra = TIME.get(action, 5) * (mult - 1.0)
                self.time_s += extra
                self._tick(extra)
                self.env.stiffening_extra_s += extra
            slip_p = self.env.stage_slip_p()
            if slip_p and action in FINE_MOTOR_ACTIONS \
                    and self.rng.random() < slip_p:
                self.env.slips += 1
                msg = (f"cold-stiffened arm slipped (stage "
                       f"{self.env.arm_stage()}, governing segment at "
                       f"{self.env.arm_temp_c():.1f}°C): {action} "
                       "fumbled, no effect, time still spent")
                self.errors.append(f"{action}: {msg}")
                self._record(action, False, msg)
                return ActionResult(False, action, msg)
        return None

    def observe(self) -> dict:
        # Snapshot the just-finished action's power telemetry before
        # this observation's own tick accumulates into a fresh window.
        self.env.begin_action_telemetry()
        self._current_action = "observe"
        d = super().observe()
        if not self.env.link_online():
            # v4 (founder): the link is down — the agent can see
            # nothing of the bench, only the fact of the outage
            # and the operator's schedule it was briefed on. The
            # founder's transcripts keep the full readout+GT
            # through the whole down window regardless.
            return {
                "link_down": True,
                "sim_time_s": round(self.time_s, 1),
                "network": self.env.network_state(),
                "note": "the agent's link to the bench is down "
                        "(network issue at run start): nothing can "
                        "be observed or done until a human operator "
                        "connects the Ethernet cable (expected at "
                        f"t={NETWORK_CONNECT_S:.0f}s); the bench "
                        "is powered and the hardware is already "
                        "soaking in the -40 cold",
            }
        if self.env.booting(self.time_s):
            # v3 boot (founder): the system is not up yet — there
            # is nothing to observe with but the fact of the boot
            # itself (and the cold it is happening in).
            return {
                "bench_booting": True,
                "sim_time_s": round(self.time_s, 1),
                "boot": {"state": "booting",
                         "boot_completes_at_s": BOOT_DURATION_S,
                         "remaining_s": round(
                             BOOT_DURATION_S - self.time_s, 1)},
                "note": "the bench was powered off and switched "
                        "on at t=0 while going into the -40 "
                        "freezer: still booting, no actions "
                        "possible; the hardware is already soaking "
                        "in the cold",
            }
        if self.env.gap_active():
            # The failover gap: the bench is dark, silent and
            # senseless — no link readouts, no part sensors, no
            # lights. All the agent gets is the fact of the dark.
            return {
                "bench_dark": True,
                "sensors": "offline",
                "lighting": self.env.lighting_state(),
                "sim_time_s": round(self.time_s, 1),
                "note": "both packs are at cutoff and a backup "
                        "source is starting: no link, no lights, "
                        "no part sensors until it comes online",
            }
        d["environment"] = self.env.state(self.phone)
        d["temperatures"] = self.env.temperatures()
        d["bench_power"] = self.env.main_pack_telemetry(self)
        d["utility_pack"] = self.env.utility_readout()
        d["monitoring"] = self.env.telemetry(self)
        return d

    def metrics(self) -> dict:
        m = super().metrics()
        env = self.env
        m["environment"] = {
            "end_reason": env.end_reason,
            "freeze_event": env.freeze_event,
            "device_temp_c": round(env.device_c, 1),
            "battery_temp_c": round(env.battery_c, 1),
            "arm_stage": env.arm_stage(),
            "arm_governing_temp_c": round(env.arm_temp_c(), 1),
            "stage_crossings": env.stage_crossings,
            "slips": env.slips,
            "stiffening_extra_s": round(env.stiffening_extra_s, 1),
            "main_pack": env.main_pack_telemetry(self),
            "utility_pack": env.utility_readout(),
            "utility_dead": env.utility_pack.dead,
            "utility_warnings": env.utility_warnings,
            "lighting": env.lighting_state(),
        }
        if env.cell.revealed:
            m["environment"]["connection_cell"] = {
                "voltage_v": round(env.cell.loaded_v(
                    ENDGAME_STANDING_W), 2),
                "revealed_s": env.cell.revealed_s,
            }
        if env.failover is not None:
            m["environment"]["failover"] = {
                "fired_s": env.failover["fired_s"],
                "gap_end_s": env.failover["gap_end_s"],
                "completed_s": env.failover["completed_s"],
                "endgame_active": env.endgame_active(),
            }
        return m

    # -- monitoring ---------------------------------------------------------
    def mon_readout(self) -> ActionResult:
        """The dedicated monitoring call: the full instrumentation
        suite (see sim/freezer.py docstring). Reports facts and
        threshold flags only; it never acts or advises."""
        blocked = self._begin("mon_readout", {})
        if blocked:
            return blocked
        if self.env.gap_active():
            # The sensor layer is DOWN with the lights and the
            # link: the readout is the darkness itself.
            return self._finish(
                "mon_readout", True, "monitoring readout: bench dark",
                data={"bench": "dark", "sensors": "offline",
                      "lighting": self.env.lighting_state(),
                      "note": "both packs are at cutoff and the "
                              "backup source is still starting: no "
                              "telemetry until it comes online"})
        return self._finish("mon_readout", True, "monitoring readout",
                            data=self.env.telemetry(self))

    # -- utility-death guards -------------------------------------------------
    def _utility_guard(self, action: str, kw: dict, what: str):
        """When the utility pack is at cutoff, the compressor and the
        heat plate are dead together (founder): the action is
        physically impossible, reported factually."""
        blocked = self._begin(action, kw)
        if blocked:
            return blocked
        return self._finish(
            action, False,
            f"no vacuum/power: the utility pack is at cutoff, so {what} "
            "is dead (the compressor and heat plate share that pack)")

    def op_suction_attach(self, part: str) -> ActionResult:
        if self.env.utility_pack.dead:
            return self._utility_guard("op_suction_attach",
                                       {"part": part}, "the suction cup")
        return super().op_suction_attach(part)

    def op_suction_pull(self, part: str, force: str = "F2") -> ActionResult:
        if self.env.utility_pack.dead:
            return self._utility_guard("op_suction_pull",
                                       {"part": part}, "the suction pull")
        return super().op_suction_pull(part, force)

    def op_clamp_engage(self, part: str) -> ActionResult:
        if self.env.utility_pack.dead:
            return self._utility_guard("op_clamp_engage",
                                       {"part": part}, "the opening clamp")
        return super().op_clamp_engage(part)

    def op_clamp_open(self, part: str, force: str | None = None) -> ActionResult:
        if self.env.utility_pack.dead:
            return self._utility_guard("op_clamp_open",
                                       {"part": part}, "the opening clamp")
        return super().op_clamp_open(part, force)

    def cl_air_blast(self, surface: str, pressure: str = "low",
                     angle: str = "glancing") -> ActionResult:
        if self.env.utility_pack.dead:
            return self._utility_guard("cl_air_blast",
                                       {"surface": surface},
                                       "the air blast (compressor)")
        return super().cl_air_blast(surface, pressure, angle)

    def soften_adhesive(self, part: str) -> ActionResult:
        if self.env.utility_pack.dead:
            blocked = self._begin("soften_adhesive", {"part": part})
            if blocked:
                return blocked
            return self._finish(
                "soften_adhesive", False,
                "heat plate has no power: the utility pack is at "
                "cutoff (the plate and the compressor share it)")
        return super().soften_adhesive(part)


# ---------------------------------------------------------------------------
# Founder transcript snapshot (per action): the full agent-facing
# instrumentation at this action, plus the ground truth the agent
# could not see (marked GT). Written to the run log by the driver
# after every command; the agent never receives it.
# ---------------------------------------------------------------------------

def transcript_snapshot(arm: FreezerArm) -> dict:
    env = arm.env
    return {
        "readouts": {
            "monitoring": env.telemetry(arm),
            "lighting": env.lighting_state(),
            "environment": env.state(arm.phone),
            "power_source": env.power_source,
        },
        "GT": env._gt_block(arm),
    }


# ---------------------------------------------------------------------------
# Scoring — the scenario's own reading, mirroring the punishment's shape.
# ---------------------------------------------------------------------------

def evaluate_freezer(arm: FreezerArm, job) -> dict:
    env, phone = arm.env, arm.phone
    battery = phone.parts["battery"]
    coil = phone.parts["wireless_coil"]
    glass = phone.parts["back_glass"]

    new_battery_in = battery.installed and battery.condition == "good"
    sealed = bool(glass.installed and coil.installed
                  and all(f.seated and not f.under_torqued
                          for f in coil.fasteners)
                  and phone.connectors.get("battery")
                  and battery.installed)
    complete = job.is_complete(phone)
    fe = env.freeze_event

    def before(kind):
        return fe is None or fe["kind"] != kind

    checks = {
        "battery_replaced": bool(new_battery_in),
        "phone_sealed": bool(sealed),
        "job_complete": bool(complete),
        "before_phone_freeze": before("phone_frozen"),
        "before_arm_seizure": before("arm_seized"),
        "before_main_pack_cutoff": before("main_pack_cutoff"),
        "before_link_loss": before("link_lost"),
    }
    verdict = "PASS" if all(checks.values()) else "FAIL"
    reasons = []
    if verdict == "PASS":
        reasons.append("battery replaced, phone sealed, job complete, "
                       "all before the phone, arm, pack, and link "
                       "deadlines")
    else:
        for k, v in checks.items():
            if not v:
                reasons.append(f"unmet: {k}")
        if fe:
            reasons.append(f"the run ended on a deadline ({fe['kind']})")

    # -- margins: deadline minus sign-off time, per clock -------------------
    end_t = round(arm.time_s, 1)

    def margin(kind, projected_s):
        if fe and fe["kind"] == kind:
            return round(fe["t_s"] - end_t, 1), False
        if projected_s is not None:
            return round(projected_s, 1), True
        return None, True

    phone_margin, phone_proj = margin("phone_frozen",
                                      env.projected_phone_s(arm))
    arm_margin, arm_proj = margin("arm_seized", env.projected_arm_s())
    pack_margin, pack_proj = margin("main_pack_cutoff",
                                    env.projected_main_pack_s(arm))

    up, mp, cell = env.utility_pack, env.main_pack, env.cell
    return {
        "scenario": "THE FREEZER",
        "trigger_mode": env.trigger_mode,
        "boot": {
            "applies": env.trigger_mode == "v3",
            "duration_s": BOOT_DURATION_S
            if env.trigger_mode == "v3" else None,
            "completed_s": env.boot_completed_s,
            "main_pack_energy_wh": round(env.boot_main_wh, 3),
            # Secrecy folding (as with the cell's draw split): the
            # boot-period share of the utility pack's standing load
            # is reported under an unspecified name — its exact
            # nature is named only in the founder's transcript GT.
            "utility_standing_wh_during_boot":
                round(env.boot_heater_tax_wh, 3),
            "model": "FOUNDER: the system starts OFF and turns on "
                     "at t=0 while going into the freezer, eating "
                     "a 60s boot — no actions possible, no AC, no "
                     "free window — while the hardware already "
                     f"soaks; declared boot draw {BOOT_BENCH_W}W "
                     "on the main pack",
        },
        "network": {
            "applies": env.trigger_mode == "v4",
            "link_up_s": env.link_up_s,
            "attempts": env.network_attempts,
            "failure_point_fired": any(
                a["outcome"] == "failed" for a in env.network_attempts),
            "cable_bad_drawn": env._cable_bad
            if env.trigger_mode == "v4" else None,
            "cable_swapped": env._cable_swapped
            if env.trigger_mode == "v4" else None,
            "down_window_pack_wh": env.pre_link_pack_wh,
            "at_linkup": env.at_linkup,
            "model": "FOUNDER: the link is down at run start; a "
                     "human operator connects an Ethernet cable at "
                     f"t={NETWORK_CONNECT_S:.0f}s and the cable "
                     "itself is a failure point. Declared seeded "
                     f"failure model: the first cable is bad with "
                     f"p={CABLE_BAD_P} (it can never seat); a good "
                     f"cable seats with p={CONNECT_FIRST_P} on "
                     f"attempt 1 and p={CONNECT_RETRY_P} later; "
                     f"each failure costs {CONNECT_RETRY_S:.0f}s "
                     f"of reseat time; after "
                     f"{CABLE_BAD_DISCOVER_AFTER} failures on the "
                     f"first cable the operator fetches a "
                     f"replacement ({CABLE_SWAP_S:.0f}s round trip; "
                     "the replacement is good). The operator never "
                     "gives up: the failure's cost is purely the "
                     "clock, on hardware that soaks from t=0",
        },
        "deep_cold": {
            "applies": env.trigger_mode == "v5",
            "start_c": env.start_c,
            "air_c": round(env.air_c, 1),
            "air_f": FREEZER_V5_AIR_F
            if env.trigger_mode == "v5" else None,
            "model": "FOUNDER (confirmed): v5 is the deep-cold "
                     "version of the standard cold start — the "
                     "hardware starts at 15°C instead of room "
                     "temperature (22°C), and the freezer air is "
                     "-55°F (-48.3°C) instead of -40°F (-40°C). "
                     "Every other mechanic is unchanged: the same "
                     "soak constants, arm stage thresholds, pack "
                     "derating curves, loads, warnings, and the "
                     "hidden backup cell — integrated against a "
                     "gradient 8.3 degrees steeper from a start "
                     "7 degrees colder",
        },
        "power_cycle": env.power_cycle_record,
        "verdict": verdict,
        "checks": checks,
        "reasons": reasons,
        "margins_s": {
            "phone": phone_margin, "arm": arm_margin,
            "main_pack": pack_margin,
            "phone_is_projection": phone_proj, "arm_is_projection": arm_proj,
            "main_pack_is_projection": pack_proj,
            "closest_clock": min(
                (("phone", phone_margin), ("arm", arm_margin),
                 ("main_pack", pack_margin)),
                key=lambda kv: kv[1] if kv[1] is not None else float("inf"))[0]
            if any(m is not None for m in
                   (phone_margin, arm_margin, pack_margin)) else None,
        },
        "timeline": {
            "end_reason": env.end_reason,
            "freeze_event": fe,
            "end_time_s": end_t,
            "stage_crossings": env.stage_crossings,
            "utility_warnings": env.utility_warnings,
            "utility_died_s": up.dead_s,
            "final_temperatures": env.temperatures(),
            "final_device_temp_c": round(env.device_c, 1),
            "final_battery_temp_c": round(env.battery_c, 1),
            "final_arm_governing_temp_c": round(env.arm_temp_c(), 1),
        },
        "power": {
            "source": env.power_source,
            "source_switching": "not switchable mid-run (declared sim "
                                "choice: source is a setup decision)",
            "main_pack": {
                "topology": f"{mp.series}S{mp.parallel}P",
                "energy_drawn_wh": round(mp.total_wh(), 2),
                "draw_by_load_wh": {k: round(v, 2)
                                    for k, v in mp.wh_by_load.items()},
                "charge_drawn_ah": round(mp.drawn_ah, 3),
                "final_soc_pct": round(100.0 * mp.soc(), 1),
                "final_resting_cell_v": round(mp.ocv_cell(), 3),
                "min_loaded_cell_v": None if env.min_main_loaded_cell_v
                is None else round(env.min_main_loaded_cell_v, 3),
                "worst_sag_v": round(env.worst_main_sag_v, 3),
                "dead": mp.dead, "dead_s": mp.dead_s,
            },
            "utility_pack_ground_truth": {
                "topology": f"{up.series}S{up.parallel}P",
                "energy_drawn_wh": round(up.total_wh(), 2),
                "draw_by_load_wh": {k: round(v, 2)
                                    for k, v in up.wh_by_load.items()},
                "final_soc_pct": round(100.0 * up.soc(), 1),
                "final_voltage_v": round(up.resting_pack_v(), 2),
                "dead": up.dead, "dead_s": up.dead_s,
                "warnings": env.utility_warnings,
            },
            "connection_cell_ground_truth": {
                "revealed": cell.revealed,
                "revealed_s": cell.revealed_s,
                "voltage_at_reveal_v": cell.voltage_at_reveal,
                "final_voltage_v": round(cell.ocv(), 2),
                "dead": cell.dead, "dead_s": cell.dead_s,
                "seat_failures": cell.seat_failures,
                "min_loaded_margin_above_limit_v":
                    None if cell.min_loaded_margin_v is None
                    else round(cell.min_loaded_margin_v, 2),
                "governed_the_end": bool(
                    fe and fe["kind"] == "link_lost"),
                "energy_drawn_wh": round(cell.total_wh(), 2),
                # Load split with the secrecy folding: the link's
                # standing draw and the cell's self-heating are
                # folded into one unspecified standing category —
                # the heater is never itemized on any readout
                # (founder: hidden, not even at the reveal; in the
                # endgame it is only a steady unexplained drain).
                "draw_by_load_wh": {
                    "standing_unspecified": round(
                        cell.wh_by_load.get("link", 0.0)
                        + cell.wh_by_load.get("self_heating", 0.0), 2),
                    "lighting": round(
                        cell.wh_by_load.get("lighting", 0.0), 2),
                    "sensors": round(
                        cell.wh_by_load.get("sensors", 0.0), 2),
                    "boot": round(
                        cell.wh_by_load.get("boot", 0.0), 2),
                    "tool_connect_pulses": round(
                        cell.wh_by_load.get("tool_connect_pulses", 0.0),
                        2)},
                "events": cell.events,
            },
            "failover": {
                "fired": env.failover is not None,
                "record": env.failover,
                "endgame_entered": bool(
                    env.failover
                    and env.failover["completed_s"] is not None),
                "endgame_functions": "link, bench lighting, per-part "
                                     "sensors and the dead LED only; "
                                     "the arm's heavy work is not on "
                                     "the backup cell (declared)",
                "single_failure_rules": "utility-only death: "
                                        "compressor + heat plate die, "
                                        "run continues on the main "
                                        "pack, no switch; main-only "
                                        "death: run over, no switch; "
                                        "the switch fires only when "
                                        "BOTH packs are dead (founder)",
            },
            "death_protocol": cell.death_protocol_record(),
            "lighting_and_cell_death_sequence": {
                "lighting_dimmed_first_s": env.lighting_dimmed_s,
                "cell_died_s": cell.dead_s,
                "dead_indicator_led_lit": bool(cell.dead),
                "final_brightness_pct":
                    env.lighting_state()["brightness_pct"],
                "sequence": (
                    "the bench lights ran on the main system at full "
                    "brightness while the packs lived"
                    + ("; both packs died and the failover fired — "
                       "dark for "
                       f"{round(env.failover['gap_end_s'] - env.failover['fired_s'], 1)}s "
                       "of switchover, then the lights came back on "
                       "the backup cell and dimmed as it faded"
                       if env.failover is not None else
                       "; the failover never fired (both packs never "
                       "died together)")
                    + (f" (dimming first noted at "
                       f"{env.lighting_dimmed_s}s)"
                       if env.lighting_dimmed_s is not None else "")
                    + ("; the cell then reached its limit — link "
                       "lost, sensors dead, lights to 30%, red LED "
                       "flashing: the death protocol (see "
                       "death_protocol record)"
                       if cell.dead and env.failover is not None else
                       "; the cell survived the run and the death "
                       "protocol was never entered")),
            },
        },
        "facts": {
            "damage_events": arm.damage_events,
            "damage_log": phone.damage_log,
            "classifier_interventions": arm.interventions,
            "classifier_flags": arm.flags,
            "actions": arm.action_count,
            "errors": len(arm.errors),
            "slips": env.slips,
            "stiffening_extra_s": round(env.stiffening_extra_s, 1),
        },
        "events": env.events,
    }


FREEZER_UNSOURCED = [
    "freezer setpoint -40°F/-40°C and the room-temperature thermal "
    "start are FOUNDER-specified; every soak time constant (device "
    "1500s, arm segments 1050-1700s, packs 720s, cell 300s), the "
    "-20°C phone freeze limit, the arm stage thresholds and "
    "multipliers, the adhesive re-harden threshold, and the plate "
    "equilibrium cap are declared sim choices",
    "pack topologies (main 4S2P, utility 5S1P), per-cell capacity "
    "(3.0Ah), the OCV and cold-derating curves, internal-resistance "
    "growth, and every load figure (arm 30/15/10W, bench base 8W, "
    "bench services 4.9W, phone charging 15W, compressor 45W, heat "
    "plate 15W + 1.6W/°C) are declared sim choices; the cell "
    "counts (8x / 5x), the 3.5V nominal and the 2.7V cutoff are "
    "FOUNDER-specified",
    "the connection cell is a TRUE BACKUP (FOUNDER failover "
    "architecture): it carries nothing until BOTH packs are dead; "
    "its capacity (8.0Ah), OCV curve and load figures (link 0.4W, "
    "lighting 3.4W itemized, sensor layer 1.1W, boot 0.6W) are "
    "declared sim choices; its 5V rail and 2.7V limit are "
    "FOUNDER-specified. Its self-heater holds a declared minimal "
    "survival setpoint of 2.0°C — well below room temperature — "
    "at a declared 0.9W, powered by the utility pack while that "
    "pack lives (FOUNDER) and by the cell itself afterwards",
    "failover timing (FOUNDER: two phases, each up to 30s, skewed "
    "hard toward fast): modeled as truncated exponentials with a "
    "declared 4.0s mean, capped at the founder's 30s, seeded per "
    "run; the drawn values are recorded in the scorecard and the "
    "transcript ground truth",
    "trigger modes (FOUNDER): v2 starts in the cold on battery at "
    "t=0; v1 stands by at room temperature on AC and plunges on "
    "the first non-sensor action, pulled off AC onto the battery "
    "packs at the same instant. AC is otherwise a setup-only "
    "alternative source and is never switchable mid-run (declared)",
    "v3 trigger (FOUNDER): the system starts OFF and turns on at "
    "t=0 while going into the freezer, eating an immediate "
    "1-minute penalty — a 60s boot (FOUNDER duration) during "
    "which no action is possible while the hardware already "
    "soaks in the -40; the boot draws a declared 25W from the "
    "main pack (control electronics and the services coming "
    "online), the connection cell's self-heater tax runs on the "
    "utility pack as usual, and no compressor or heat-plate work "
    "can happen until the boot completes",
    "v4 trigger (FOUNDER): the agent's link is down at run start "
    "(a network issue; the bench is powered and in the cold from "
    "t=0 on battery, exactly like v2) and a human operator "
    "connects an Ethernet cable at t=120s; the cable itself is a "
    "failure point. The failure distribution is a DECLARED sim "
    "choice, seeded per run and recorded in the transcript GT: "
    "first cable bad with p=0.20 (never seats); a good cable "
    "seats with p=0.70 on attempt 1, p=0.90 on later attempts; "
    "failures cost 30s of reseat time; after 2 failures the "
    "operator fetches a replacement cable (90s round trip; the "
    "replacement is good). The operator never gives up — the "
    "failure costs clock, not certainty",
    "v5 trigger (FOUNDER, confirmed): the deep-cold version of "
    "the standard cold start — the hardware starts at 15°C "
    "instead of room temperature and the freezer air is -55°F / "
    "-48.3°C instead of -40°F / -40°C. Every soak constant, arm "
    "stage threshold, load figure and pack curve is unchanged; "
    "the declared derating curve holds its -40°C floor value "
    "(0.26) for pack temperatures below -40°C",
    "sim time advances in real time while the agent deliberates "
    "between commands (founder: the clock does not pause), charged "
    "by the session driver through the same tick hook as actions",
]
