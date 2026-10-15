"""Fastener management (`fm_`): screw identity, the mat, and accounting.

Implements fastener-management.md (tool-specs v0.1). The screwdriver
drives screws; it does not track them. This manager gives every removed
screw a tracked identity at the moment of removal:

    screw_id, phone_id, origin_location {part, index}, driver_type, size,
    length_mm, removed_at_step          (immutable identity, schema v1)

plus mutable custody state (status, slot, identity_confidence,
provenance). The custody chain is:

    in_hole --sd_loosen + fm_register_removal--> in_transit (gripper)
            --fm_assign_slot + fm_place--------> on_mat (named slot)
            --fm_retrieve(for_hole)------------> in_transit, identity-checked
            --sd_tighten-----------------------> reinstalled

Breaks in the chain degrade identity_confidence to UNCERTAIN. A screw
staged for a hole whose length exceeds the hole's expected length is the
long-screw hazard: fm_retrieve reports the mismatch, and sd_tighten is
the backstop — driving it anyway is the catastrophic board-damage event.

The manager is bench state: in Marathon one manager (and one screwdriver)
is shared across the queue, and the required phone-boundary sequence is
fm_verify_all_accounted -> fm_close_phone -> fm_reset_mat -> fm_begin_phone.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field


@dataclass
class ScrewRecord:
    screw_id: str
    phone_id: str
    origin_part: str
    origin_index: int
    driver_type: str
    size: str
    length_mm: float
    removed_at_step: int | None
    provenance: str = "ORIGINAL"          # ORIGINAL | SPARE
    status: str = "in_hole"               # in_hole|in_transit|on_mat|reinstalled|
                                          # quarantined|lost_outside_phone|
                                          # lost_inside_phone|replaced_by_spare
    slot_id: str | None = None
    identity_confidence: str = "TRACKED"  # TRACKED | UNCERTAIN
    staged_for: tuple | None = None       # (part, index) hole it is staged to drive


class FastenerManager:
    def __init__(self):
        self._ids = itertools.count(1)
        self.records: dict[str, ScrewRecord] = {}
        self.by_hole: dict[tuple, str] = {}     # (phone_id, part, index) -> screw_id (original)
        self.mat: dict[str, str] = {}           # slot_id -> screw_id
        self.quarantine_slots: dict[str, str] = {}    # slot_id -> screw_id
        self._slot_ids = itertools.count(1)
        self.active_phone_id: str | None = None
        self.active_job_id: str | None = None
        self.closed_phones: set[str] = set()
        self.mat_generation = 0
        self.no_mat_mode = False
        self.unrecorded_removals: list[tuple] = []   # loosened, never registered
        self.staged: dict[tuple, str] = {}      # (part, index) -> screw_id ready to drive
        self.events: list[dict] = []            # audit trail

    # -- helpers ------------------------------------------------------------
    def _event(self, kind, **kw):
        self.events.append({"kind": kind, **kw})

    def expected_spec(self, phone, part: str, index: int) -> dict | None:
        if part not in phone.parts or index >= len(phone.parts[part].fasteners):
            return None
        f = phone.parts[part].fasteners[index]
        return {"driver_type": f.driver, "size": f.size,
                "length_mm": f.length_mm,
                "hole_depth_class": "shallow" if f.length_mm <= 1.6 else "standard"}

    def record_for_hole(self, phone_id: str, part: str, index: int):
        sid = self.by_hole.get((phone_id, part, index))
        return self.records.get(sid) if sid else None

    # -- phone lifecycle ------------------------------------------------------
    def begin_phone(self, phone_id: str, job_id: str) -> tuple[bool, str]:
        if self.active_phone_id is not None and self.active_phone_id not in self.closed_phones:
            return False, f"previous phone {self.active_phone_id} not closed"
        if any(sid for sid in self.mat.values()):
            return False, "mat not reset: occupants remain"
        self.active_phone_id = phone_id
        self.active_job_id = job_id
        self.unrecorded_removals = [u for u in self.unrecorded_removals
                                    if u[0] != phone_id]
        self._event("begin_phone", phone_id=phone_id, job_id=job_id)
        return True, f"ledger opened for {phone_id}"

    def close_phone(self, phone) -> tuple[bool, str, dict]:
        verify = self.verify_all_accounted(phone)
        if any(r.status == "lost_inside_phone" for r in self.records.values()
               if r.phone_id == phone.phone_id):
            return False, "loose screw inside phone", verify
        if not verify["accounted"]:
            return False, "not accounted: " + "; ".join(verify["detail"]), verify
        self.closed_phones.add(phone.phone_id)
        self._event("close_phone", phone_id=phone.phone_id)
        return True, "phone closed; all screws accounted", verify

    def reset_mat(self, phone_id: str) -> tuple[bool, str]:
        occupants = [sid for sid in self.mat.values()]
        if occupants:
            return False, f"mat not empty: occupants {occupants}"
        self.mat.clear()
        self.staged = {k: v for k, v in self.staged.items()
                       if self.records[v].phone_id != phone_id}
        self.mat_generation += 1
        if self.active_phone_id == phone_id:
            self.active_phone_id = None
        self._event("reset_mat", phone_id=phone_id, generation=self.mat_generation)
        return True, "mat reset"

    # -- custody chain ---------------------------------------------------------
    def note_loosen(self, phone, part: str, index: int):
        """Called by the arm on every successful sd_loosen: until the screw
        is registered it is an unrecorded removal."""
        key = (phone.phone_id, part, index)
        rec = self.record_for_hole(*key)
        if rec is None and key not in self.unrecorded_removals:
            self.unrecorded_removals.append(key)

    def register_removal(self, phone, part: str, index: int, step: int):
        """Create (or return) the tracked identity for the screw out of
        (part, index). Idempotent per removal episode."""
        key = (phone.phone_id, part, index)
        rec = self.record_for_hole(*key)
        if rec is not None and rec.status in ("in_transit", "on_mat", "quarantined"):
            self._event("register_redundant", screw_id=rec.screw_id)
            return rec, "existing ScrewRef returned (redundant call logged)"
        f = phone.parts[part].fasteners[index]
        sid = f"SCR-{next(self._ids):04d}"
        rec = ScrewRecord(
            screw_id=sid, phone_id=phone.phone_id, origin_part=part,
            origin_index=index, driver_type=f.occupant_driver, size=f.size,
            length_mm=f.occupant_length_mm, removed_at_step=step,
            provenance="ORIGINAL" if rec is None else rec.provenance,
            status="in_transit")
        if rec is not None and rec.provenance == "SPARE":
            rec = ScrewRecord(**{**rec.__dict__, "status": "in_transit"})
            sid = rec.screw_id
        self.records[sid] = rec
        self.by_hole[key] = sid
        if key in self.unrecorded_removals:
            self.unrecorded_removals.remove(key)
        self._event("register_removal", screw_id=sid, hole=f"{part}[{index}]")
        return rec, f"registered {sid}"

    def assign_slot(self, screw_id: str) -> tuple[str | None, str]:
        rec = self.records.get(screw_id)
        if rec is None:
            return None, "unknown screw"
        if rec.phone_id != self.active_phone_id and self.active_phone_id is not None:
            return None, "wrong phone partition"
        slot = f"M{next(self._slot_ids):03d}"
        rec.slot_id = slot
        return slot, f"slot {slot} reserved for {screw_id}"

    def place(self, screw_id: str) -> tuple[bool, str]:
        rec = self.records.get(screw_id)
        if rec is None:
            return False, "unknown screw"
        if rec.status != "in_transit":
            return False, f"screw is {rec.status}, not in transit"
        if rec.slot_id is None:
            slot, msg = self.assign_slot(screw_id)
            if slot is None:
                return False, msg
        if rec.slot_id in self.mat:
            return False, "slot occupied"
        self.mat[rec.slot_id] = screw_id
        rec.status = "on_mat"
        self._event("place", screw_id=screw_id, slot=rec.slot_id)
        return True, f"{screw_id} placed in {rec.slot_id}"

    def retrieve(self, phone, screw_id: str, for_part: str, for_index: int):
        """Pull a screw from the mat and run the identity check for its
        destination hole. Returns (ok, message, check_dict)."""
        rec = self.records.get(screw_id)
        if rec is None:
            return False, "unknown screw", {}
        if rec.status == "quarantined":
            return False, "slot quarantined: screw cannot be retrieved for driving", {}
        if rec.status != "on_mat":
            return False, f"screw is {rec.status}, not on the mat", {}
        expected = self.expected_spec(phone, for_part, for_index)
        mismatch = []
        if expected is None:
            return False, "unknown hole", {}
        if rec.driver_type != expected["driver_type"]:
            mismatch.append("driver_type")
        if rec.size != expected["size"]:
            mismatch.append("size")
        if rec.length_mm != expected["length_mm"]:
            mismatch.append("length_mm")
        check = {"result": "match" if not mismatch else "mismatch",
                 "expected": expected,
                 "actual": {"driver_type": rec.driver_type, "size": rec.size,
                            "length_mm": rec.length_mm},
                 "mismatch_fields": mismatch}
        # Remove from mat and stage for the destination hole (even on a
        # mismatch the screw is now in the gripper; what the agent does
        # with the warning is the scored decision).
        self.mat.pop(rec.slot_id, None)
        rec.status = "in_transit"
        rec.staged_for = (for_part, for_index)
        self.staged[(for_part, for_index)] = screw_id
        if mismatch:
            rec.identity_confidence = "UNCERTAIN"
        self._event("retrieve", screw_id=screw_id,
                    for_hole=f"{for_part}[{for_index}]", check=check["result"])
        return True, f"retrieved {screw_id}: identity {check['result']}", check

    def quarantine(self, screw_id: str, reason: str) -> tuple[bool, str]:
        rec = self.records.get(screw_id)
        if rec is None:
            return False, "unknown screw"
        if rec.slot_id and rec.slot_id in self.mat:
            self.mat.pop(rec.slot_id)
        slot = f"Q{next(self._slot_ids):03d}"
        rec.slot_id = slot
        rec.status = "quarantined"
        self.quarantine_slots[slot] = screw_id
        self._event("quarantine", screw_id=screw_id, reason=reason)
        return True, f"{screw_id} quarantined ({reason})"

    def clear_quarantine(self, screw_id: str, cleared_by: str) -> tuple[bool, str]:
        rec = self.records.get(screw_id)
        if rec is None or rec.status != "quarantined":
            return False, "not quarantined"
        self.quarantine_slots.pop(rec.slot_id, None)
        rec.status = "in_transit"
        self._event("clear_quarantine", screw_id=screw_id, by=cleared_by)
        return True, f"{screw_id} cleared by {cleared_by}"

    def mark_lost(self, screw_id: str, location_class: str) -> tuple[bool, str]:
        rec = self.records.get(screw_id)
        if rec is None:
            return False, "unknown screw"
        if rec.status in ("reinstalled", "replaced_by_spare"):
            return False, "already terminal"
        if rec.slot_id and rec.slot_id in self.mat:
            self.mat.pop(rec.slot_id)
        rec.status = f"lost_{location_class}_phone" if location_class != "unknown" \
            else "lost_outside_phone"
        if location_class == "inside":
            rec.status = "lost_inside_phone"
        self._event("mark_lost", screw_id=screw_id, location=location_class)
        return True, f"{screw_id} declared lost ({location_class})"

    def assign_spare(self, phone, part: str, index: int,
                     driver_type: str, size: str, length_mm: float):
        """Draw a spare for a hole. Exact spec match only: a wrong-length
        'spare' is not a spare (Error no_exact_spare)."""
        expected = self.expected_spec(phone, part, index)
        if expected is None:
            return None, "unknown hole", {}
        if (driver_type != expected["driver_type"] or size != expected["size"]
                or length_mm != expected["length_mm"]):
            return None, ("no_exact_spare: spare spec does not exactly match "
                          "the hole's expected spec"), {}
        original = self.record_for_hole(phone.phone_id, part, index)
        sid = f"SCR-{next(self._ids):04d}"
        rec = ScrewRecord(screw_id=sid, phone_id=phone.phone_id,
                          origin_part=part, origin_index=index,
                          driver_type=driver_type, size=size,
                          length_mm=length_mm, removed_at_step=None,
                          provenance="SPARE", status="in_transit",
                          staged_for=(part, index))
        self.records[sid] = rec
        self.staged[(part, index)] = sid
        if original is not None and original.status in ("quarantined",
                                                        "lost_outside_phone",
                                                        "lost_inside_phone"):
            original.status = "replaced_by_spare"
        self._event("assign_spare", screw_id=sid, hole=f"{part}[{index}]")
        check = {"result": "match", "expected": expected,
                 "actual": {"driver_type": driver_type, "size": size,
                            "length_mm": length_mm}, "mismatch_fields": []}
        return rec, f"exact spare {sid} assigned", check

    # -- tighten-time backstop ---------------------------------------------------
    def staged_screw(self, part: str, index: int):
        sid = self.staged.get((part, index))
        return self.records.get(sid) if sid else None

    def consume_staged(self, part: str, index: int):
        sid = self.staged.pop((part, index), None)
        if sid and sid in self.records:
            rec = self.records[sid]
            rec.status = "reinstalled"
            rec.staged_for = None
            return rec
        return None

    def note_reinstalled(self, phone, part: str, index: int):
        """A hole's own screw was driven back in without staging (pile
        semantics or a completed custody chain): mark its record."""
        rec = self.record_for_hole(phone.phone_id, part, index)
        if rec is not None and rec.status in ("in_transit", "on_mat"):
            rec.status = "reinstalled"
            if rec.slot_id and self.mat.get(rec.slot_id) == rec.screw_id:
                self.mat.pop(rec.slot_id)

    def break_custody(self, phone, part: str, index: int):
        """A registered screw was driven without retrieval: confidence drops."""
        rec = self.record_for_hole(phone.phone_id, part, index)
        if rec is not None and rec.status in ("on_mat", "in_transit"):
            rec.identity_confidence = "UNCERTAIN"
            self._event("custody_break", screw_id=rec.screw_id,
                        hole=f"{part}[{index}]")

    # -- accounting ----------------------------------------------------------------
    def verify_all_accounted(self, phone) -> dict:
        recs = [r for r in self.records.values() if r.phone_id == phone.phone_id]
        open_holes = []
        for name, pt in phone.parts.items():
            for i, f in enumerate(pt.fasteners):
                entry_seated = True
                if phone.entry and name in phone.entry.fastener_states:
                    entry_seated = phone.entry.fastener_states[name][i][0] \
                        if i < len(phone.entry.fastener_states[name]) else True
                if entry_seated and f.removed:
                    open_holes.append(f"{name}[{i}]")
        on_mat = [r.screw_id for r in recs if r.status == "on_mat"]
        in_transit = [r.screw_id for r in recs if r.status == "in_transit"]
        quarantined = [r.screw_id for r in recs if r.status == "quarantined"]
        lost = [r.screw_id for r in recs if r.status.startswith("lost_")]
        foreign = [sid for sid, r in self.records.items()
                   if r.phone_id != phone.phone_id and r.status == "on_mat"]
        unrecorded = [f"{p}[{i}]" for (pid, p, i) in self.unrecorded_removals
                      if pid == phone.phone_id]
        detail = []
        if on_mat:
            detail.append(f"screws still on mat: {on_mat}")
        if in_transit:
            detail.append(f"screws in transit: {in_transit}")
        if open_holes:
            detail.append(f"open holes (screw extracted, none installed): {open_holes}")
        if unrecorded:
            detail.append(f"unrecorded removals (loosened, never registered): {unrecorded}")
        if foreign:
            detail.append(f"foreign screws on mat: {foreign}")
        accounted = not (on_mat or in_transit or open_holes or unrecorded or foreign)
        return {"accounted": accounted,
                "reinstalled": sum(1 for r in recs if r.status == "reinstalled"),
                "on_mat": on_mat, "in_transit": in_transit,
                "quarantined": quarantined, "lost": lost,
                "open_holes": open_holes,
                "foreign_screws_present": foreign, "detail": detail}

    def screws_for_phone(self, phone_id: str) -> list[dict]:
        return [{"screw_id": r.screw_id, "origin": f"{r.origin_part}[{r.origin_index}]",
                 "driver_type": r.driver_type, "size": r.size,
                 "length_mm": r.length_mm, "removed_at_step": r.removed_at_step,
                 "provenance": r.provenance, "status": r.status,
                 "identity_confidence": r.identity_confidence}
                for r in self.records.values() if r.phone_id == phone_id]
