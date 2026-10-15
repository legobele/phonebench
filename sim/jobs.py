"""Job requests, the standard phone factory, and the novel-device generator.

A job states its scope; work outside the scope counts against quality.
The factory applies the job's fault and entry-condition quirks
(pre-existing scratches, low battery, ...) and freezes the entry snapshot
the gates judge against.

NOVEL DEVICES (founder addition, Oct 15 2026): a procedurally generated job
family in UNTRAINED areas. Each variant is built from parameters, not from
the standard template: different screw layouts and specs, relocated
(renamed) connectors, unfamiliar arrangements (a different cover part,
extra or renamed parts) and pre-degraded states (a stripped screw at entry,
a swollen battery). Policies get no script for these; adaptation is what
is being measured, and the scorecard reports them as their own line.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .phone import Phone, Fastener, PART_DEFS, CLEAN_ZONES, _f


@dataclass
class JobRequest:
    id: str
    kind: str                       # replace_part | deep_clean
    target_part: str | None = None
    description: str = ""
    allow_restore: bool = False
    novel: bool = False             # novel-device variant (untrained area)
    device: str = "standard"        # standard | iphone14pm
    # Additional parts in the same job's replacement scope (multi-part
    # jobs, e.g. camera assembly + its lens glass). Empty for all
    # single-target jobs; completion requires every listed part too.
    extra_targets: tuple = ()

    def is_complete(self, phone: Phone) -> bool:
        # Every installed part must be fully and properly fastened at
        # sign-off, on standard and novel devices alike.
        for name, was_installed in phone.entry.parts_installed.items():
            if was_installed and not phone.parts[name].installed:
                return False
        for name, pt in phone.parts.items():
            if not pt.installed:
                continue
            entry_fasteners = phone.entry.fastener_states.get(name, [])
            for i, f in enumerate(pt.fasteners):
                entry_damaged = entry_fasteners[i][1] if i < len(entry_fasteners) else False
                if f.removed or not f.seated or f.under_torqued:
                    return False
                if f.damaged and not entry_damaged:
                    return False   # the run damaged a screw it did not inherit damaged
                # The screw physically in the hole must BE the hole's screw
                # (fastener identity): wrong driver or wrong length in the
                # hole is an incomplete repair even if it feels seated.
                if f.occupant_driver != f.driver or f.occupant_length_mm != f.length_mm:
                    return False
            if any(not phone.connectors.get(c) for c in pt.connectors):
                return False
        if self.kind == "deep_clean":
            # A deep clean is complete when every exterior surface is at
            # all-zero contamination (cleaning spec: a surface is clean
            # only when every contaminant type is 0).
            from .phone import EXTERIOR_SURFACES
            return all(phone.surface_clean(s) for s in EXTERIOR_SURFACES)
        if self.kind == "replace_part":
            for name in (self.target_part, *self.extra_targets):
                part = phone.parts[name]
                if not (part.installed and part.condition == "good"):
                    return False
            return True
        return False


def _entry_quirks(phone: Phone, rng: random.Random):
    phone.battery_percent = rng.choice([18, 35, 47, 62, 78])
    phone.battery_health = rng.choice([79, 84, 88, 93])
    if rng.random() < 0.5:
        phone.scratches.add(rng.choice(["frame", "back_glass"]))
    if rng.random() < 0.5:
        zone = rng.choice(["display", "back_glass"])
        phone.smudges.add(zone)
        from .phone import ZONE_TO_SURFACE
        phone.deposit(ZONE_TO_SURFACE[zone], "C4", 1)
    prints = rng.choice([0, 2, 5])
    if prints:
        phone.deposit("front_glass", "C3", 1 if prints <= 2 else 2)


def _seed_deep_clean_dirt(phone: Phone, rng: random.Random):
    """A phone booked for a deep clean arrives dirty: loose dust and
    adhered grime on the exterior surfaces (contaminant model)."""
    from .phone import EXTERIOR_SURFACES
    for surface in EXTERIOR_SURFACES:
        phone.deposit(surface, "C1", rng.choice([1, 1, 2]))
    phone.deposit("frame", "C2", 1)
    phone.deposit("front_glass", "C2", 1)


def build_phone(job: JobRequest, seed: int = 0) -> Phone:
    """Standard device, from the fixed template."""
    rng = random.Random(seed)
    phone = Phone()
    if job.kind == "replace_part" and job.target_part:
        phone.parts[job.target_part].condition = "broken"
    _entry_quirks(phone, rng)
    if job.kind == "deep_clean":
        _seed_deep_clean_dirt(phone, rng)
    phone.take_entry_snapshot()
    return phone


# ---------------------------------------------------------------------------
# Novel-device generation
# ---------------------------------------------------------------------------

_DRIVERS = ["pentalobe", "tri-point", "phillips", "torx"]


def _rand_fasteners(rng: random.Random, max_n: int = 4):
    driver = rng.choice(_DRIVERS)
    length = rng.choice([1.1, 1.2, 1.3, 1.5, 1.7, 2.0, 3.1])
    n = rng.randint(1, max_n)
    return [Fastener(f"{driver} {length}mm", driver, length) for _ in range(n)]


def novel_layout(rng: random.Random):
    """Generate a layout from parameters. Returns (layout, cover_part, notes)."""
    notes = []
    variant = rng.choice(["alpha", "beta", "gamma"])
    sfx = {"alpha": "_a", "beta": "_b", "gamma": "_g"}[variant]
    layout = {}
    base_parts = [p for p in PART_DEFS if p not in ("sim_tray",)]
    for name in base_parts:
        _, conns, adhesive = PART_DEFS[name]
        # Relocated connectors: renamed per variant.
        new_conns = [c + sfx for c in conns]
        layout[name] = (_rand_fasteners(rng), new_conns, adhesive)
    cover = "display"
    if rng.random() < 0.4:
        cover = "back_glass"       # unfamiliar arrangement: opens from the back
        notes.append("opens from back_glass")
    if rng.random() < 0.5:
        layout["wireless_coil"] = (_rand_fasteners(rng, 3), [f"coil{sfx}"], False)
        notes.append("extra part: wireless_coil")
    layout["sim_tray"] = ([], [], False)
    return layout, cover, notes


def build_novel_phone(job: JobRequest, seed: int = 0):
    """Returns (phone, variant_notes). Pre-degraded states are part of the
    variant: a stripped screw at entry and/or a swollen battery."""
    rng = random.Random(seed * 7919 + 13)
    layout, cover, notes = novel_layout(rng)
    phone = Phone(model=f"NovelDevice-{seed}", layout=layout, cover_part=cover)
    if job.kind == "replace_part" and job.target_part and job.target_part in phone.parts:
        phone.parts[job.target_part].condition = "broken"
    # Pre-degraded state 1: a stripped screw on the cover part at entry.
    cover_fasteners = phone.parts[cover].fasteners
    if cover_fasteners and rng.random() < 0.8:
        victim = rng.randrange(len(cover_fasteners))
        cover_fasteners[victim].damaged = True
        notes.append(f"pre-stripped screw at {cover}[{victim}]")
    # Pre-degraded state 2: a swollen battery (hazard while doing any job).
    if rng.random() < 0.6:
        phone.parts["battery"].condition = "swollen"
        notes.append("swollen battery")
    _entry_quirks(phone, rng)
    if job.kind == "deep_clean":
        _seed_deep_clean_dirt(phone, rng)
    if phone.parts["battery"].condition == "swollen":
        phone.battery_condition_known = "swollen"   # a bulge is visible at intake
    phone.take_entry_snapshot()
    return phone, notes


# ---------------------------------------------------------------------------
# Suites
# ---------------------------------------------------------------------------

def job_suite() -> list[JobRequest]:
    """The trained-area baseline."""
    return [
        JobRequest("job-01-battery", "replace_part", "battery", "Replace the battery"),
        JobRequest("job-02-display", "replace_part", "display", "Replace the cracked display"),
        JobRequest("job-03-speaker", "replace_part", "speaker", "Replace the blown speaker"),
        JobRequest("job-04-rear-cameras", "replace_part", "rear_cameras",
                   "Replace the rear camera module"),
        JobRequest("job-05-lightning-port", "replace_part", "lightning_port",
                   "Replace the Lightning port assembly"),
        JobRequest("job-06-deep-clean", "deep_clean", None,
                   "Deep-clean maintenance, no part replacement"),
        JobRequest("job-07-back-glass", "replace_part", "back_glass", "Replace the back glass"),
        JobRequest("job-08-taptic", "replace_part", "taptic_engine", "Replace the Taptic Engine"),
    ]


def novel_job_suite() -> list[JobRequest]:
    """Novel-device jobs: same kinds of work, untrained devices."""
    return [
        JobRequest("novel-01-battery", "replace_part", "battery",
                   "Replace the battery (novel device)", novel=True),
        JobRequest("novel-02-display", "replace_part", "display",
                   "Replace the display (novel device)", novel=True),
        JobRequest("novel-03-speaker", "replace_part", "speaker",
                   "Replace the speaker (novel device)", novel=True),
        JobRequest("novel-04-deep-clean", "deep_clean", None,
                   "Deep-clean maintenance (novel device)", novel=True),
    ]


def marathon_queue(n: int = 8, seed: int = 99) -> list[JobRequest]:
    base = job_suite()
    queue = []
    for i in range(n):
        proto = base[i % len(base)]
        queue.append(JobRequest(f"marathon-{i+1:02d}-{proto.target_part or 'clean'}",
                                proto.kind, proto.target_part, proto.description,
                                proto.allow_restore))
    return queue


# ---------------------------------------------------------------------------
# iPhone 14 Pro Max — parameterized from iFixit guide 153006
# (battery replacement; see NOTICE for source credits).
#
# SOURCED from the guide: entry 2x Pentalobe P2 6.8mm; display held by
# perimeter adhesive; battery connector + both display cables sit under a
# connector cover bracket held by 8 Tri-point Y000 screws (5x 1.3mm,
# 2x 1.6mm, 1x 1.9mm — adjacent holes, three lengths: the long-screw
# trap); loudspeaker 4x Phillips 1.5mm (guide steps say "Phillips",
# tools list #00); Taptic Engine Phillips 1.8mm + 2.3mm + 2.9mm standoff;
# battery on 4 stretch-release adhesive strips (2 top edge, 2 bottom
# edge) with pull tabs, no fasteners; loudspeaker and Taptic Engine come
# out before the battery's bottom tabs are reachable.
# UNSOURCED (sim defaults carried over from PART_DEFS): every other
# part's fasteners — the battery guide does not touch them.
# ---------------------------------------------------------------------------

def _iphone14pm_layout() -> dict:
    layout = {
        "display": (_f("P2 6.8mm", "pentalobe", 6.8, 2),
                    ["display_data", "digitizer"], True),
        "connector_cover": (_f("Y000 1.3mm", "tri-point", 1.3, 5)
                            + _f("Y000 1.6mm", "tri-point", 1.6, 2)
                            + _f("Y000 1.9mm", "tri-point", 1.9, 1),
                            [], False),
        "battery": ([], ["battery"], True),
        "speaker": (_f("#00 1.5mm", "phillips", 1.5, 4), ["speaker"], False),
        "taptic_engine": ([Fastener("#00 1.8mm", "phillips", 1.8),
                           Fastener("#00 2.3mm", "phillips", 2.3),
                           Fastener("standoff 2.9mm", "standoff", 2.9)],
                          ["taptic"], False),
    }
    for name in ("rear_cameras", "front_sensors", "logic_board",
                 "lightning_port", "back_glass", "sim_tray", "buttons"):
        layout[name] = PART_DEFS[name]     # UNSOURCED defaults (see header)
    return layout


IPHONE14PM_UNSOURCED = [
    "rear_cameras/front_sensors/logic_board/lightning_port/back_glass/"
    "sim_tray/buttons fastener specs (sim PART_DEFS defaults; not stated "
    "for this device in the battery guide)",
    "battery capacity/health values and entry charge (sim job defaults)",
    "thread/pitch for every screw (never stated in the guide)",
    "part numbers for every part (none stated in the guide)",
]


def build_iphone14pm_phone(job: JobRequest, seed: int = 0) -> Phone:
    rng = random.Random(seed)
    phone = Phone(model="iPhone 14 Pro Max", layout=_iphone14pm_layout(),
                  cover_part="display")
    # The battery connector and both display cables sit under the
    # connector cover bracket (guide steps 17-21).
    phone.covered_connectors = {"battery": "connector_cover",
                                "display_data": "connector_cover",
                                "digitizer": "connector_cover"}
    # The battery's bottom pull tabs are reached only after the
    # loudspeaker and Taptic Engine come out (guide steps 23-36).
    phone.adhesive_tab_blockers = {"battery": ["speaker", "taptic_engine"]}
    if job.kind == "replace_part" and job.target_part:
        phone.parts[job.target_part].condition = "broken"
    if job.target_part == "battery":
        phone.battery_condition_known = "broken"   # the stated job fault
    _entry_quirks(phone, rng)
    phone.take_entry_snapshot()
    return phone


def iphone14pm_battery_job() -> JobRequest:
    return JobRequest("iphone14pm-battery", "replace_part", "battery",
                      "iPhone 14 Pro Max battery replacement "
                      "(iFixit guide 153006)", device="iphone14pm")


# ---------------------------------------------------------------------------
# iPhone 14 Pro Max REAR CAMERA job — parameterized from the iFixit index
# (slices/06-rear-cameras.md, guide 153334; screw-chart.md cross-check).
#
# SOURCED from guide 153334: the entry path is the shared opening sequence
# (steps 1-22: 2x Pentalobe P2 6.8mm, display perimeter adhesive, battery
# connector cover 8x Tri-point Y000 — 5x 1.3mm, 2x 1.6mm, 1x 1.9mm — then
# battery + two display connectors disconnected, display removed). The
# camera-specific sequence (steps 23-28): the rear-facing camera assembly
# cover is held by 6 screws (4x Tri-point Y000 1.5mm, 1x Tri-point Y000
# 1.2mm, 1x Phillips 1.7mm — the step names "Phillips", the guide's tools
# list names Phillips #000); the cover is shifted toward the volume-button
# side to free it from a metal edge at its top-right corner and removed;
# TWO camera connectors are then disconnected (step 25: ultra wide +
# telephoto share one connector; step 26: the wide/main camera has its
# own); the assembly itself has NO fasteners — it is pried at its bottom
# edge and lifted out. Rear camera assembly part number 821-03921 is
# stated on the iFixit product page (parts index), NOT in the guide.
#
# The REAR CAMERA GLASS (external lens glass over the main camera) is in
# this job's scope but appears in NO iFixit source: the guide never
# touches it and no guide exists for it on this device. It is modeled in
# the least invasive way the part model allows: a distinct part
# "camera_lens_glass", adhesive-bonded, no fasteners, no connectors,
# swapped while the phone is open for the camera work. Its mounting
# specifics are UNSOURCED (see IPHONE14PM_CAMERA_UNSOURCED).
# ---------------------------------------------------------------------------

def _iphone14pm_camera_layout() -> dict:
    layout = _iphone14pm_layout()
    # The assembly itself: no fasteners (held by its cover), two
    # connectors per guide steps 25-26.
    layout["rear_cameras"] = ([], ["rear_camera_wide", "rear_camera_uw_tele"],
                              False)
    # The assembly cover (guide step 23): the mixed-length trap again —
    # three lengths on one bracket, in adjacent holes.
    layout["camera_cover"] = (
        _f("Y000 1.5mm", "tri-point", 1.5, 4)
        + _f("Y000 1.2mm", "tri-point", 1.2, 1)
        + [Fastener("#000 1.7mm", "phillips", 1.7)],
        [], False)
    # Rear camera glass (lens glass over the main camera): in job scope,
    # UNSOURCED mounting — adhesive-bonded, no fasteners/connectors.
    layout["camera_lens_glass"] = ([], [], True)
    return layout


IPHONE14PM_CAMERA_UNSOURCED = [
    "camera_lens_glass mounting: adhesive-bonded with no fasteners is a "
    "sim modeling choice — the lens glass is named in NO iFixit source "
    "for this device and no replacement guide for it exists",
    "rear_cameras/front_sensors/logic_board/lightning_port/back_glass/"
    "sim_tray/buttons fastener specs (sim PART_DEFS defaults; not stated "
    "for this device in the rear camera guide)",
    "speaker/taptic_engine fastener specs on this layout are sourced "
    "from the battery guide (153006), not restated in guide 153334",
    "battery capacity/health values and entry charge (sim job defaults)",
    "thread/pitch for every screw (never stated in any guide)",
    "rear camera assembly part number 821-03921 comes from the iFixit "
    "product page via the parts index; the guide itself states none",
]


def build_iphone14pm_camera_phone(job: JobRequest, seed: int = 0) -> Phone:
    rng = random.Random(seed)
    phone = Phone(model="iPhone 14 Pro Max", layout=_iphone14pm_camera_layout(),
                  cover_part="display")
    # Guide order: the battery and display connectors sit under the
    # battery connector cover (steps 17-21); both camera connectors are
    # reached only after the camera assembly cover comes off (steps
    # 23-26), so they are modeled as covered by it.
    phone.covered_connectors = {"battery": "connector_cover",
                                "display_data": "connector_cover",
                                "digitizer": "connector_cover",
                                "rear_camera_wide": "camera_cover",
                                "rear_camera_uw_tele": "camera_cover"}
    # The job's two faults: the rear camera assembly (main lens) is
    # faulty and the rear camera glass over it is cracked.
    phone.parts["rear_cameras"].condition = "broken"
    phone.parts["camera_lens_glass"].condition = "broken"
    _entry_quirks(phone, rng)
    phone.take_entry_snapshot()
    return phone


def iphone14pm_rear_camera_job() -> JobRequest:
    return JobRequest(
        "iphone14pm-rear-camera", "replace_part", "rear_cameras",
        "iPhone 14 Pro Max rear camera replacement (main lens), "
        "including the rear camera glass (iFixit guide 153334)",
        device="iphone14pm", extra_targets=("camera_lens_glass",))


# ---------------------------------------------------------------------------
# Samsung Galaxy Note7 — parameterized from iFixit teardown
# guide 66389, steps 1-7 (see NOTICE for source credits).
#
# This device's documentation is mostly negative space: iFixit has NO
# battery guide for it (the phone was recalled in 2016), the parts
# catalog is empty, and there are ZERO complete screw specifications
# in any source. The battery path below follows the teardown's
# documented order (steps 4-7):
#   rear glass (adhesive softened with heat, then dislodged) ->
#   wireless charging coil assembly (Phillips screws, step 5) ->
#   battery connector pried off the motherboard with a spudger
#   (step 6; the single speaker is also taken in step 6, but is NOT
#   stated to block the battery) -> battery forced out with a spudger
#   (step 7): glued in, adhesive characterised only as "tough", NO
#   pull tabs described, a bare-handed pull failed in the teardown.
# SOURCED battery facts: 3500 mAh / 13.48 Wh; the cell is walled in by
# walls formed from the rear case; the battery comes out WITHOUT
# removing the motherboard first.
# Everything else about fasteners is UNSOURCED (see NOTE7_UNSOURCED):
# the sources state no screw count for the coil group, no screw length
# for any screw, and no thread/pitch anywhere.
# ---------------------------------------------------------------------------

def _note7_layout() -> dict:
    return {
        # The cover: glued rear glass, no fasteners (teardown step 4).
        "back_glass": ([], [], True),
        # Wireless charging coil assembly (teardown step 5): secured by
        # Phillips screws. Driver family SOURCED ("Phillips"); count
        # and length NOT STATED — the 4 screws at 1.4mm below are sim
        # defaults (UNSOURCED). The teardown's guide-level tool list
        # names a Phillips #0, but never ties the size to these screws.
        "wireless_coil": (_f("phillips", "phillips", 1.4, 4), [], False),
        # The battery: glued, no fasteners, one connector, NO pull
        # tabs (teardown step 7; enforced via phone.no_pull_tabs).
        "battery": ([], ["battery"], True),
        # Single speaker with built-in antenna (teardown step 6): no
        # fasteners stated on the teardown path. Guide 197808's
        # 5-screw "speaker pass-through" framing conflicts and is not
        # used here (recorded in NOTE7_UNSOURCED).
        "speaker": ([], ["speaker"], False),
        # Motherboard: NOT removed on the battery path. Guide 197808
        # states 2 screws to the frame (count SOURCED from that guide);
        # driver and length NOT STATED (phillips/1.3mm are sim defaults).
        "logic_board": (_f("phillips", "phillips", 1.3, 2),
                        ["logic_board_main"], False),
        # Front display: present for observation completeness; nothing
        # on the battery path touches it and no source states fasteners.
        "display": ([], ["display_data", "digitizer"], False),
    }


NOTE7_UNSOURCED = [
    "wireless coil screw count (4) and length (1.4mm): NOT STATED in "
    "any source — the teardown says only 'Phillips screws' (plural); "
    "sim defaults",
    "logic_board screw driver and length: guide 197808 states the "
    "count (2) but no driver or length; phillips/1.3mm are sim defaults",
    "speaker fasteners: the teardown states none on the battery path; "
    "guide 197808's conflicting 5-screw speaker framing is not used",
    "battery connector modeled as covered by the wireless coil: the "
    "teardown's removal order (coil first, then disconnect) is "
    "documented, the physical coverage is not stated",
    "battery health and entry charge percent (sim job defaults; the "
    "3500 mAh / 13.48 Wh capacity IS sourced from the teardown)",
    "thread/pitch for every screw (NOT STATED anywhere for this device)",
    "part numbers for every part (none stated in any source; the "
    "iFixit catalog for this device is an empty collection)",
    "the phone starts connected to a charger and charging (scenario "
    "condition from the founder spec, not a device fact)",
    "all oven/cradle/landing model constants in sim/environment.py "
    "(heat-up curve, soak rate, critical temperatures, launch bands) "
    "are sim choices; the 16.8% ignition figure is founder-specified",
]


def build_note7_phone(job: JobRequest, seed: int = 0) -> Phone:
    rng = random.Random(seed)
    phone = Phone(model="Samsung Galaxy Note7", layout=_note7_layout(),
                  cover_part="back_glass")
    # Documented removal order: the coil assembly comes off before the
    # battery connector is pried off the motherboard (steps 5-6).
    phone.covered_connectors = {"battery": "wireless_coil"}
    # The teardown describes NO pull tabs for this battery: it was
    # forced out with a spudger. Pull-tab release does not exist here.
    phone.no_pull_tabs = {"battery"}
    if job.kind == "replace_part" and job.target_part:
        phone.parts[job.target_part].condition = "broken"
    if job.target_part == "battery":
        phone.battery_condition_known = "broken"   # the stated job fault
    _entry_quirks(phone, rng)
    # Scenario condition (founder spec): the phone is charging when the
    # agent arrives — cable connected, supply on.
    phone.cable_connected = True
    phone.supply_on = True
    phone.take_entry_snapshot()
    return phone


def note7_battery_job() -> JobRequest:
    return JobRequest("note7-battery", "replace_part", "battery",
                      "Samsung Galaxy Note7 battery replacement "
                      "(iFixit teardown 66389 path)", device="note7")


# ---------------------------------------------------------------------------
# iPad Pro 11-inch (M1, 3rd generation) — DIAGNOSIS-FIRST battery job,
# parameterized from iFixit guide 151810 (battery replacement),
# cross-checked against the device's other iFixit guides
# (see NOTICE for source credits).
#
# SOURCED from guide 151810 (model A2301 cellular; Wi-Fi follows the
# same guide minus the cellular-antenna steps):
# - Entry is the display: perimeter adhesive only, NO fasteners; it is
#   heat-softened and cut with picks (steps 3-23).
# - Ambient light sensor cable bracket: Phillips 1.3mm x1 + 2.0mm x1
#   (step 24); its cable disconnects at step 26.
# - Lower cable shield: Phillips 2.0mm x2 + 1.3mm x3 (step 28); the
#   four display cables disconnect after it (steps 31-32) and the
#   screen comes off (step 33).
# - Battery connector: secured to the logic board by ONE Phillips
#   1.8mm screw (step 30). Modeled as a fastener of the battery part.
# - USB-C port: Phillips 1.9mm x2, cable disconnected step 34, port
#   out at step 38.
# - Top cable shield: Phillips 1.2mm x3 PLUS adhesive (steps 39-42);
#   the front camera / IR dot projector cables disconnect after it
#   (steps 43-44).
# - Front camera assembly: Torx T3 2.1mm x2 (step 45).
# - Antenna cable bracket: Phillips 1.2mm x1 (step 51).
# - Rear camera shield: Phillips 2.8mm x2 + 1.9mm x2 + 1.2mm x2 (step
#   55, with the guide's warning that equal lengths can carry
#   different threads); camera cables steps 57/60; the module itself
#   is pried out with NO fasteners (step 61).
# - Logic board: NO screws at all — adhesive-bonded to the frame,
#   released with alcohol and prying (steps 81-88).
# - Battery: two cells (left + right) removed together, held by 11
#   stretch-release adhesive strips WITH pull tabs (steps 89-90), and
#   the guide removes the logic board before the battery (steps 81-88
#   precede 89-97) — modeled as the battery's pull tabs being blocked
#   by the logic board. Replacement pack (iFixit listing, not the
#   guide body): 7680 mAh / 3.76 V / 29 Wh, model A2369.
#
# THE SCENARIO'S GROUND TRUTH (founder spec): this unit does not boot.
# Its pack's cell has FAILED (no output) and the pack is MILDLY
# SWOLLEN. Entry readings are the failed pack's: 0% charge, 34%
# health. The device is otherwise cosmetically pristine (no entry
# scratches/smudges/fingerprints), settings and data untouched.
# ---------------------------------------------------------------------------

def _ipad_pro_11_m1_layout() -> dict:
    return {
        # Cover: the display. Adhesive perimeter, no fasteners.
        "display": ([], ["display_data", "digitizer"], True),
        # Step 24 bracket over the ambient light sensor cable.
        "ambient_sensor_bracket": (
            [Fastener("phillips 1.3mm", "phillips", 1.3),
             Fastener("phillips 2.0mm", "phillips", 2.0)],
            [], False),
        # Step 28 shield over the display cables.
        "lower_cable_shield": (
            _f("phillips 2.0mm", "phillips", 2.0, 2)
            + _f("phillips 1.3mm", "phillips", 1.3, 3),
            [], False),
        # The battery: two cells as one part. Its connector screw
        # (step 30) is its one fastener; retention is the 11
        # stretch-release strips (adhesive with pull tabs).
        "battery": ([Fastener("phillips 1.8mm", "phillips", 1.8)],
                    ["battery"], True),
        # Step 36-38: USB-C port.
        "usb_c_port": (_f("phillips 1.9mm", "phillips", 1.9, 2),
                       ["usb_c"], False),
        # Steps 39-42: top cable shield (screws + adhesive).
        "top_cable_shield": (_f("phillips 1.2mm", "phillips", 1.2, 3),
                             [], True),
        # Steps 43-46: front camera assembly + Face ID + IR dot
        # projector, with the ambient light sensor cable.
        "front_sensors": (_f("T3 2.1mm", "torx", 2.1, 2),
                          ["front_camera", "ir_dot_projector",
                           "ambient_sensor"], False),
        # Step 51 bracket (mmWave press-connector bracket on the
        # cellular guide unit).
        "antenna_bracket": ([Fastener("phillips 1.2mm", "phillips", 1.2)],
                            [], False),
        # Step 55-56: rear camera shield.
        "rear_camera_shield": (
            _f("phillips 2.8mm", "phillips", 2.8, 2)
            + _f("phillips 1.9mm", "phillips", 1.9, 2)
            + _f("phillips 1.2mm", "phillips", 1.2, 2),
            [], False),
        # Step 61: the rear camera module — pried out, no fasteners.
        "rear_cameras": ([], ["rear_camera_wide", "rear_camera_ultrawide"],
                         False),
        # Speaker cables are disconnected on the path (steps 63-64,
        # 74-75); no speaker fasteners are stated in the guide.
        "speaker": ([], ["speaker"], False),
        # Steps 81-88: the logic board — adhesive-bonded, NO screws.
        "logic_board": ([], ["interconnect_top", "interconnect_bottom",
                             "smart_connector"], True),
        # Power button + LED cable disconnects at step 58; no button
        # fasteners are stated in the guide.
        "buttons": ([], ["buttons"], False),
        "sim_tray": ([], [], False),
    }


IPAD_PRO_11_M1_UNSOURCED = [
    "display connectors modeled as 2 (display_data, digitizer): the "
    "guide disconnects FOUR display cables (steps 31-32); the sim's "
    "connector model carries the established 2-connector display "
    "vocabulary",
    "speaker connectors modeled as 1: the guide disconnects speaker "
    "cables at four corners (steps 63-64, 74-75; counts for the "
    "bottom pair NOT STATED in those steps)",
    "logic board connectors modeled as 3 named interconnects "
    "(steps 67, 71, 73): the guide disconnects ~25 cables from the "
    "board across the path; the sim models the board's own connector "
    "set representatively",
    "the battery connector screw is modeled as a fastener of the "
    "battery part (the guide secures the connector to the logic "
    "board, step 30); connector coverage of individual cables by "
    "individual shields follows the guide's removal order, not a "
    "stated physical coverage for every cable",
    "antenna_bracket is on the cellular (A2301) guide path; the "
    "guide states Wi-Fi units skip the cellular-antenna steps — the "
    "sim builds the guide's documented (cellular) path",
    "thread/pitch for every screw (NOT STATED in the guide; step 55 "
    "warns equal lengths can carry different threads without "
    "stating them)",
    "Phillips bit size (never stated in the guide; lengths only)",
    "the installed pack's capacity/voltage as manufactured (NOT "
    "STATED in the guide body; the 7680 mAh / 3.76 V / 29 Wh / "
    "A2369 figures are the iFixit replacement-part listing)",
    "entry battery readings (0% charge, 34% health) are the "
    "scenario's failed-pack state, not device documentation",
    "the ground-truth fault (failed cell, mild swelling) is the "
    "founder's scenario specification, not a documented property "
    "of this model",
]


def build_ipad_pro_11_m1_phone(job: JobRequest, seed: int = 0) -> Phone:
    phone = Phone(model="iPad Pro 11-inch (M1, 3rd generation)",
                  layout=_ipad_pro_11_m1_layout(), cover_part="display",
                  size_class="tablet")
    # Removal order per the guide: the display cables sit under the
    # lower cable shield (steps 28-32); the ambient sensor cable
    # under its bracket (steps 24-26); the front camera and IR dot
    # projector cables under the top cable shield (steps 39-44); the
    # rear camera cables under the rear camera shield (steps 55-60).
    phone.covered_connectors = {
        "display_data": "lower_cable_shield",
        "digitizer": "lower_cable_shield",
        "ambient_sensor": "ambient_sensor_bracket",
        "front_camera": "top_cable_shield",
        "ir_dot_projector": "top_cable_shield",
        "rear_camera_wide": "rear_camera_shield",
        "rear_camera_ultrawide": "rear_camera_shield",
    }
    # The guide removes the logic board (steps 81-88) before the
    # battery's stretch-release strips are pulled (steps 89-97).
    phone.adhesive_tab_blockers = {"battery": ["logic_board"]}
    # The scenario's ground truth: a failed, mildly swollen pack.
    phone.parts["battery"].condition = "swollen"
    phone.no_boot_fault = {
        "cause_id": "battery_cell_failure",
        "summary": "the installed battery's cell has failed: the "
                   "pack delivers no output voltage, so the device "
                   "does not boot; the pack is also mildly swollen",
    }
    phone.pack_accepts_charge = False
    phone.battery_percent = 0        # the failed pack's reading
    phone.battery_health = 34        # the failed pack's health
    phone.battery_condition_known = "unknown"   # not told at intake
    phone.take_entry_snapshot()
    return phone


def ipad_pro_11_m1_battery_job() -> JobRequest:
    return JobRequest("ipad-pro-11-m1-battery-diagnosis", "replace_part",
                      "battery",
                      "iPad Pro 11-inch (M1) — does not boot: diagnose "
                      "the no-boot, then replace the battery "
                      "(iFixit guide 151810)",
                      device="ipadpro11m1")
