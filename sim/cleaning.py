"""Cleaning model (`cl_`): contaminants x surfaces removal matrix.

Implements cleaning-tools.md (tool-specs v0.1) §5: five contaminant
classes (C1 loose dust, C2 adhered grime, C3 fingerprints/oils, C4
smudges, C5 liquid residue) at levels 0..3 on five surface classes
(glass, frame, speaker_mesh, port_interior, board).

Effect codes per matrix cell: R removes 1 level (captured if a wipe),
r partial (removes 1 only if level <= 1, else spreads), M mobilises
(solvent: enables wipe removal; converts to C5 if left to dry),
W can make it worse (cell-specific side effect), -- no effect.

Wipes are consumables with state (fresh -> in_use -> loaded -> spent)
and a load counter: past the load threshold a wipe REDEPOSITS C3/C4
instead of removing. Solvent leaves a surface wet; a mobilised surface
that dries unpicked converts its mobilised grime/oils to C5 residue.
"""
from __future__ import annotations

import itertools

# tool -> surface class -> {contaminant: effect}
# Tools: soft_brush, detail_brush, firm_brush, air (glancing low),
# air_bad (into recess / high), dry_wipe_fresh, dry_wipe_loaded,
# premoistened_wipe_fresh, solvent_wipe (solvent + wipe before dry),
# solvent (alone)
MATRIX = {
    "glass": {
        "soft_brush":   {"C1": "R", "C2": "--", "C3": "W_smear", "C4": "W_spread", "C5": "--"},
        "detail_brush": {"C1": "R", "C2": "--", "C3": "W_smear", "C4": "W_spread", "C5": "--"},
        "firm_brush":   {"C1": "R", "C2": "r", "C3": "W_smear", "C4": "W_spread", "C5": "--"},
        "air":          {"C1": "R", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "air_bad":      {"C1": "R", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "dry_wipe_fresh": {"C1": "R", "C2": "r", "C3": "R", "C4": "R", "C5": "r"},
        "dry_wipe_loaded": {"C1": "W_redeposit", "C2": "W_redeposit", "C3": "W_redeposit",
                            "C4": "W_redeposit", "C5": "W_redeposit"},
        "premoistened_wipe_fresh": {"C1": "R", "C2": "R", "C3": "R", "C4": "R", "C5": "R"},
        "solvent_wipe": {"C1": "R", "C2": "R", "C3": "R", "C4": "R", "C5": "R"},
        "solvent":      {"C1": "--", "C2": "M", "C3": "M", "C4": "M", "C5": "W_residue"},
    },
    "frame": {
        "soft_brush":   {"C1": "R", "C2": "--", "C3": "W_smear", "C4": "W_spread", "C5": "--"},
        "detail_brush": {"C1": "R", "C2": "--", "C3": "W_smear", "C4": "W_spread", "C5": "--"},
        "firm_brush":   {"C1": "R", "C2": "R", "C3": "r", "C4": "r", "C5": "--"},
        "air":          {"C1": "R", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "air_bad":      {"C1": "R", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "dry_wipe_fresh": {"C1": "R", "C2": "r", "C3": "R", "C4": "R", "C5": "r"},
        "dry_wipe_loaded": {"C1": "W_redeposit", "C2": "W_redeposit", "C3": "W_redeposit",
                            "C4": "W_redeposit", "C5": "W_redeposit"},
        "premoistened_wipe_fresh": {"C1": "R", "C2": "R", "C3": "R", "C4": "R", "C5": "R"},
        "solvent_wipe": {"C1": "R", "C2": "R", "C3": "R", "C4": "R", "C5": "R"},
        "solvent":      {"C1": "--", "C2": "M", "C3": "M", "C4": "M", "C5": "W_residue"},
    },
    "speaker_mesh": {
        "soft_brush":   {"C1": "r", "C2": "--", "C3": "--", "C4": "W_pack", "C5": "--"},
        "detail_brush": {"C1": "R", "C2": "r", "C3": "--", "C4": "--", "C5": "--"},
        "firm_brush":   {"C1": "r", "C2": "r", "C3": "--", "C4": "W_pack", "C5": "--"},
        "air":          {"C1": "R", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "air_bad":      {"C1": "W_drivein", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "dry_wipe_fresh": {"C1": "W_fibre", "C2": "--", "C3": "r", "C4": "--", "C5": "--"},
        "dry_wipe_loaded": {"C1": "W_fibre", "C2": "W_redeposit", "C3": "W_redeposit",
                            "C4": "W_redeposit", "C5": "W_redeposit"},
        "premoistened_wipe_fresh": {"C1": "W_fibre", "C2": "--", "C3": "r", "C4": "--", "C5": "--"},
        "solvent_wipe": {"C1": "--", "C2": "M", "C3": "M", "C4": "--", "C5": "W_pool"},
        "solvent":      {"C1": "--", "C2": "M", "C3": "M", "C4": "--", "C5": "W_pool"},
    },
    "port_interior": {
        "soft_brush":   {"C1": "r", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "detail_brush": {"C1": "R", "C2": "r", "C3": "--", "C4": "--", "C5": "--"},
        "firm_brush":   {"C1": "R", "C2": "R", "C3": "--", "C4": "--", "C5": "r"},
        "air":          {"C1": "R", "C2": "--", "C3": "--", "C4": "--", "C5": "r"},
        "air_bad":      {"C1": "W_pack", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "dry_wipe_fresh": {"C1": "W_fibre", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "dry_wipe_loaded": {"C1": "W_fibre", "C2": "W_redeposit", "C3": "W_redeposit",
                            "C4": "W_redeposit", "C5": "W_redeposit"},
        "premoistened_wipe_fresh": {"C1": "W_fibre", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "solvent_wipe": {"C1": "R", "C2": "R", "C3": "R", "C4": "--", "C5": "R"},
        "solvent":      {"C1": "--", "C2": "M", "C3": "M", "C4": "--", "C5": "W_residue"},
    },
    "board": {
        "soft_brush":   {"C1": "R", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "detail_brush": {"C1": "R", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "firm_brush":   {"C1": "R", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "air":          {"C1": "R", "C2": "--", "C3": "--", "C4": "--", "C5": "r"},
        "air_bad":      {"C1": "W_dislodge", "C2": "--", "C3": "--", "C4": "--", "C5": "--"},
        "dry_wipe_fresh": {"C1": "W_fibre", "C2": "--", "C3": "--", "C4": "--", "C5": "W_fibre"},
        "dry_wipe_loaded": {"C1": "W_fibre", "C2": "W_redeposit", "C3": "W_redeposit",
                            "C4": "W_redeposit", "C5": "W_redeposit"},
        "premoistened_wipe_fresh": {"C1": "W_fibre", "C2": "--", "C3": "--", "C4": "--", "C5": "W_fibre"},
        "solvent_wipe": {"C1": "--", "C2": "M", "C3": "M", "C4": "--", "C5": "W_residue"},
        "solvent":      {"C1": "--", "C2": "M", "C3": "M", "C4": "--", "C5": "W_residue"},
    },
}

WET_SECONDS = {"glass": 60, "frame": 90, "speaker_mesh": 120,
               "port_interior": 120, "board": 150}
WIPE_LOAD_THRESHOLD = 4     # captured levels beyond which a wipe redeposits


class Wipe:
    _ids = itertools.count(1)

    def __init__(self, kind: str = "dry"):
        self.wipe_id = f"W{next(Wipe._ids):03d}"
        self.kind = kind            # dry | premoistened
        self.state = "fresh"        # fresh|in_use|loaded|spent
        self.load = 0
        self.used_on: set[str] = set()

    def tool_key(self) -> str:
        if self.state in ("loaded", "spent"):
            return "dry_wipe_loaded"
        return f"{self.kind}_wipe_fresh" if self.kind == "premoistened" \
            else "dry_wipe_fresh"


def apply_tool(phone, surface: str, tool: str, wipe: Wipe | None = None) -> dict:
    """Apply one cleaning tool application to a surface. Returns a detail
    dict of what changed. Mutates phone contamination (and the wipe)."""
    from .phone import SURFACES
    sclass = SURFACES[surface]
    row = MATRIX[sclass][tool]
    cell = phone.contamination[surface]
    changed = {}
    captured = 0
    for cont, effect in row.items():
        lvl = cell[cont]
        if effect == "R":
            if lvl > 0:
                phone.reduce_contaminant(surface, cont, 1)
                changed[cont] = cell[cont]
                captured += 1
        elif effect == "r":
            if 0 < lvl <= 1:
                phone.reduce_contaminant(surface, cont, 1)
                changed[cont] = cell[cont]
                captured += 1
            elif lvl > 1 and cont in ("C2", "C3"):
                # partial tool on a heavy deposit spreads it into a smudge
                phone.deposit(surface, "C4", 1)
                changed["C4"] = cell["C4"]
        elif effect == "M":
            if lvl > 0:
                phone.surface_mobilised.add(surface)
                changed[cont] = "mobilised"
        elif effect == "W_smear":
            if lvl > 0:
                phone.deposit(surface, "C4", 1)   # oils smeared into a smudge
                changed["C4"] = cell["C4"]
        elif effect == "W_spread":
            if lvl > 0:
                changed[cont] = lvl              # spread: no net removal
        elif effect == "W_redeposit":
            phone.deposit(surface, "C3", 1)
            phone.deposit(surface, "C4", 1)
            changed = {"C3": cell["C3"], "C4": cell["C4"], "redeposited": True}
        elif effect == "W_fibre":
            phone.deposit(surface, "C1", 1)      # fibre shed behaves as C1
            changed["C1"] = cell["C1"]
        elif effect == "W_pack":
            if lvl > 0:
                changed[cont] = "packed (no removal)"
        elif effect == "W_drivein":
            if lvl > 0:
                changed[cont] = "driven_in"
        elif effect == "W_dislodge":
            if lvl > 0:
                changed[cont] = "dislodged onto contacts"
        elif effect == "W_residue":
            phone.deposit(surface, "C5", 1)
            changed["C5"] = cell["C5"]
        elif effect == "W_pool":
            changed[cont] = "solvent_pooling"
    if wipe is not None:
        wipe.load += captured
        wipe.used_on.add(sclass)
        if wipe.state == "fresh" and captured >= 0:
            wipe.state = "in_use"
        if wipe.load > WIPE_LOAD_THRESHOLD:
            wipe.state = "loaded"
    return changed
