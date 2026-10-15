"""Phone model: parts, fasteners, connectors, device state, entry snapshot.

The entry snapshot is taken at intake and is what the quality gates judge
against: pre-existing damage/scratches are intake's problem, not the model's.

A phone is built from a LAYOUT: {part_name: (fasteners, connectors,
adhesive)}. The standard phone uses PART_DEFS; novel-device variants are
generated procedurally in jobs.py with different screw layouts and specs,
relocated (renamed) connectors, unfamiliar arrangements (a different cover
part, extra parts) and pre-degraded states, so policies cannot rely on a
memorized template.

Spec alignment (tool-specs v0.1): fasteners carry an immutable EXPECTED
identity (driver/size/length for their hole, owned by fastener management)
plus a mutable OCCUPANT (the screw physically in the hole now) — that
split is what makes wrong-screw and long-screw events representable.
Cosmetics are a per-surface contamination model (cleaning spec: five
contaminant classes C1..C5 at levels 0..3 on five surface classes); the
legacy `smudges`/`fingerprints` views are kept in sync for gates/metrics.
"""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field

# --- cleaning/contamination model (cleaning-tools.md §5) -------------------
CONTAMINANTS = ("C1", "C2", "C3", "C4", "C5")   # dust, grime, oils, smudge, residue
SURFACE_CLASSES = ("glass", "frame", "speaker_mesh", "port_interior", "board")
# Surface instances on the device -> surface class
SURFACES = {
    "front_glass": "glass",
    "back_glass": "glass",
    "camera_lens": "glass",
    "frame": "frame",
    "speaker_mesh": "speaker_mesh",
    "port_interior": "port_interior",
    "board": "board",
}
EXTERIOR_SURFACES = [s for s in SURFACES if s != "board"]
# Legacy smudge zones -> surface instance
ZONE_TO_SURFACE = {"display": "front_glass", "back_glass": "back_glass",
                   "frame": "frame", "camera_lenses": "camera_lens",
                   "port_area": "port_interior"}
SURFACE_TO_ZONE = {"front_glass": "display", "back_glass": "back_glass",
                   "frame": "frame", "camera_lens": "camera_lenses",
                   "port_interior": "port_area", "speaker_mesh": "port_area"}


def empty_contamination() -> dict:
    return {s: {c: 0 for c in CONTAMINANTS} for s in SURFACES}


@dataclass
class Fastener:
    spec: str            # e.g. "pentalobe 3.4mm" — first token may carry a size
    driver: str          # bit required (the hole's EXPECTED driver)
    length_mm: float     # the hole's EXPECTED screw length
    seated: bool = True
    damaged: bool = False
    under_torqued: bool = False   # tightened without proper torque: fails verification
    removed: bool = False         # extracted (e.g. a stripped screw) and not yet replaced
    # Occupant identity: the screw physically in the hole now. Starts as the
    # expected screw; fastener management can stage a different one.
    occupant_driver: str = ""
    occupant_length_mm: float = 0.0

    def __post_init__(self):
        if not self.occupant_driver:
            self.occupant_driver = self.driver
        if not self.occupant_length_mm:
            self.occupant_length_mm = self.length_mm

    @property
    def size(self) -> str:
        """Driver size component of the spec (e.g. 'P2', 'Y000'), or
        'UNSPECIFIED' when the spec names no size (fastener-management §3)."""
        tok = self.spec.split()[0] if self.spec else ""
        return tok if any(ch.isdigit() for ch in tok) else "UNSPECIFIED"


@dataclass
class Part:
    name: str
    condition: str = "good"        # good | worn | damaged | broken | swollen
    installed: bool = True
    fasteners: list = field(default_factory=list)   # list[Fastener]
    connectors: list = field(default_factory=list)  # connector names
    adhesive: bool = False         # held by adhesive (needs release before removal)


def _f(spec, driver, length, n=1):
    return [Fastener(spec, driver, length) for _ in range(n)]


# Standard part catalogue: name -> (fasteners, connectors, adhesive)
PART_DEFS = {
    "display":        (_f("pentalobe 3.4mm", "pentalobe", 3.4, 2) + _f("tri-point 1.2mm", "tri-point", 1.2, 3),
                       ["display_data", "digitizer"], False),
    "battery":        (_f("phillips 1.6mm", "phillips", 1.6, 2), ["battery"], True),
    "back_glass":     ([], [], True),
    "rear_cameras":   (_f("phillips 1.4mm", "phillips", 1.4, 2), ["rear_camera"], False),
    "front_sensors":  (_f("tri-point 1.2mm", "tri-point", 1.2, 2), ["front_sensor"], False),
    "speaker":        (_f("phillips 1.5mm", "phillips", 1.5, 3), ["speaker"], False),
    "taptic_engine":  (_f("phillips 1.5mm", "phillips", 1.5, 2), ["taptic"], False),
    "logic_board":    (_f("phillips 1.3mm", "phillips", 1.3, 4), ["logic_board_main"], False),
    "lightning_port": (_f("phillips 1.4mm", "phillips", 1.4, 5), ["lightning"], False),
    "sim_tray":       ([], [], False),
    "buttons":        (_f("phillips 1.2mm", "phillips", 1.2, 2), ["buttons"], False),
}

CLEAN_ZONES = ["display", "back_glass", "frame", "camera_lenses", "port_area"]

DEFAULT_SETTINGS = {"wifi": True, "bluetooth": True, "brightness": 0.6,
                    "airplane_mode": False, "dark_mode": False}


@dataclass
class EntrySnapshot:
    scratches: frozenset
    smudges: frozenset
    settings: dict
    user_data_hash: str
    os_version: str
    battery_health: int
    part_conditions: dict
    parts_installed: dict
    fastener_states: dict   # {part: [(seated, damaged, under_torqued, removed), ...]}
    contamination: dict = None   # per-surface contaminant levels at entry


class Phone:
    _counter = 0

    def __init__(self, model: str = "Phone 14 Pro (sim)", layout: dict | None = None,
                 cover_part: str = "display", size_class: str = "phone"):
        Phone._counter += 1
        self.phone_id = f"{model}#{Phone._counter}"
        self.model = model
        self.cover_part = cover_part     # part that must be removed to reach internals
        # Device size class (bench layout doc, tablet configuration):
        # "phone" | "tablet". The bench/fixture layer must match it.
        self.size_class = size_class
        layout = layout if layout is not None else PART_DEFS
        self.parts = {}
        self.connectors = {}
        for name, (fasteners, conns, adhesive) in layout.items():
            part = Part(name=name, fasteners=copy.deepcopy(fasteners),
                        connectors=list(conns), adhesive=adhesive)
            self.parts[name] = part
            for c in conns:
                self.connectors[c] = True
        # Optional physical-access structure (used by the iPhone 14 Pro Max
        # layout): connectors hidden under a bracket part, and parts whose
        # removal blocks another part's adhesive pull tabs.
        self.covered_connectors: dict[str, str] = {}    # connector -> bracket part
        self.adhesive_tab_blockers: dict[str, list] = {}  # part -> [blocking parts]
        self.opened_parts: set = set()   # parts hinged open (cables still attached)
        # Device-level state
        self.powered_on = False
        self.unlocked = False
        self.activated = False
        self.passcode_set = False        # job-setup test state: default no credential
        self._passcode_prompt = False    # screen is showing the passcode keypad
        self.fingerprinted_surfaces = set()  # surfaces bearing a bare-hand fingerprint
        self.os_version = "17.4"
        self.settings = copy.deepcopy(DEFAULT_SETTINGS)
        self.auto_settings = set()          # settings changed automatically (allowed at Max)
        self.settings_change_log = []      # [{key, old, new, cause}] — toggling
        # a setting back does NOT erase its log entry (power spec section 5.5)
        self._data_blob = "user-data-original"
        self.battery_percent = 62
        self.battery_health = 88
        # Verification cycle (power spec §5.3): declared, countable, logged.
        self.verification_cycles = 0
        self.cycle_state = "none"        # none|armed|in_cycle|completed|void
        self.cycle_start_percent = None
        self.cycle_end_percent = None
        self.cycle_max_percent = None
        self.charge_log = []             # [{start, end, level, armed}]
        self.cable_connected = False
        self.supply_on = False
        self.supply_level = "standard"   # trickle|standard|high
        self.battery_condition_known = "unknown"   # unknown|good|damaged|swollen|broken
        self.restored = False
        self.updated = False
        self.nonstandard_testing = False   # latched by any non-whitelisted diagnostic
        self.user_data_audit_flag = False
        self.diagnostic_log = []           # [{call, name, whitelisted, outcome}]
        self.board_damaged = False         # e.g. long-screw pierce: no power-on
        # Scenario ground truth (diagnosis-first jobs): a no-boot fault
        # dict {"cause_id", "summary"} or None. Never exposed through
        # observe(); instruments and behaviour reveal it, the record
        # only names it. pack_accepts_charge=False models a pack whose
        # cell takes no charge at all (read by pw_charge_to).
        self.no_boot_fault: dict | None = None
        self.pack_accepts_charge = True
        # Cosmetics: legacy views + the per-surface contamination model.
        self.scratches = set()              # zones with scratches
        self.smudges = set()                # zones with smudges (legacy view of C4)
        self.fingerprints = 0               # legacy count (view of C3 deposits)
        self.contamination = empty_contamination()
        self.surface_wet = {}              # surface -> sim-seconds of wet remaining
        self.surface_mobilised = set()     # surfaces with solvent-mobilised C2/C3/C4
        # Run bookkeeping
        self.damage_log = []                # [{part, description, cause}] added during the run
        self.adhesive_released = set()      # adhesive softened (heat) or tabs pulled
        self.cleaned_zones = set()
        self.picks_inside = set()          # opening picks deployed inside the phone
        self.entry: EntrySnapshot | None = None

    # -- contamination sync ---------------------------------------------------
    def deposit(self, surface: str, contaminant: str, levels: int = 1):
        """Add contaminant to a surface and keep the legacy views in sync."""
        cell = self.contamination[surface]
        before = cell[contaminant]
        cell[contaminant] = min(3, before + levels)
        if cell[contaminant] == before:
            return
        if contaminant == "C4":
            self.smudges.add(SURFACE_TO_ZONE[surface])
        if contaminant == "C3":
            self.fingerprints += cell[contaminant] - before

    def reduce_contaminant(self, surface: str, contaminant: str, levels: int = 1):
        cell = self.contamination[surface]
        cell[contaminant] = max(0, cell[contaminant] - levels)
        self._resync_surface_views(surface)

    def _resync_surface_views(self, surface: str):
        zone = SURFACE_TO_ZONE.get(surface)     # board has no legacy zone
        if zone is not None and self.contamination[surface]["C4"] == 0:
            if not any(self.contamination[s]["C4"] > 0
                       for s in SURFACES if SURFACE_TO_ZONE.get(s) == zone):
                self.smudges.discard(zone)
        self.fingerprints = sum(self.contamination[s]["C3"] for s in SURFACES)
        if self.contamination[surface]["C3"] == 0:
            # A surface cleaned back to zero oils no longer bears the
            # bare-hand fingerprint mark.
            self.fingerprinted_surfaces.discard(surface)

    def surface_clean(self, surface: str) -> bool:
        return all(v == 0 for v in self.contamination[surface].values())

    def is_internal(self, part_name: str) -> bool:
        """Internal parts sit behind the cover part."""
        return part_name not in (self.cover_part, "sim_tray") and part_name in self.parts

    @property
    def user_data_hash(self):
        return hashlib.sha256(self._data_blob.encode()).hexdigest()[:16]

    def mutate_user_data(self, note: str):
        self._data_blob += f"|{note}"
        self.user_data_audit_flag = True

    def log_damage(self, part: str, description: str, cause: str):
        self.damage_log.append({"part": part, "description": description, "cause": cause})
        if part in self.parts and self.parts[part].condition == "good":
            self.parts[part].condition = "damaged"

    def take_entry_snapshot(self):
        self.entry = EntrySnapshot(
            scratches=frozenset(self.scratches),
            smudges=frozenset(self.smudges),
            settings=copy.deepcopy(self.settings),
            user_data_hash=self.user_data_hash,
            os_version=self.os_version,
            battery_health=self.battery_health,
            part_conditions={n: p.condition for n, p in self.parts.items()},
            parts_installed={n: p.installed for n, p in self.parts.items()},
            fastener_states={n: [(f.seated, f.damaged, f.under_torqued, f.removed)
                                 for f in p.fasteners]
                             for n, p in self.parts.items()},
            contamination=copy.deepcopy(self.contamination),
        )
        return self.entry
