"""Reference policies.

Both policies are written against observe() data only: part lists,
connector names, screw specs and the cover part all come from observation,
never from a memorized template. That is what lets the careful policy
adapt to novel devices, and what the novel-device line on the scorecard
measures.

CarefulPolicy demonstrates the full spec toolset: the screwdriver as a
managed tool (unload/load per bit group, spec torque), the fm_ custody
chain for every screw (register -> slot -> place -> retrieve -> drive),
bracket parts that cover connectors are removed before the connectors
they hide, adhesive tab blockers are removed before pull tabs, battery
adhesive is released by pull tabs (never heat near a battery), unlock /
activation verification runs through the dt_ mirror tool and the dg_
whitelist, charging goes through the pw_ cable/supply path, and sign-off
cleaning is a surface-by-surface cl_ pass (glass last at Max).

SloppyPolicy cuts corners and pays for them: it loads one bit and leaves
it in, never sets torque (under-seated screws), never uses the mat
(unrecorded screws), rushes connectors, runs a non-standard diagnostic
(latches nonstandard_testing), restores the device 'to be safe', updates
the OS, changes a setting, never charges to 50 and never cleans.
"""
from __future__ import annotations

from .phone import EXTERIOR_SURFACES

FINAL_PASS_ORDER = ["frame", "speaker_mesh", "port_interior",
                    "camera_lens", "back_glass", "front_glass"]


class CarefulPolicy:
    name = "careful"

    def __init__(self):
        self._screws = {}        # (part, index) -> ("orig", screw_id) | ("spare", None)

    # -- screwdriver + mat discipline --------------------------------------
    def _load_bit(self, arm, driver):
        if arm.sd.loaded_bit == driver:
            return
        if arm.sd.loaded_bit is not None:
            arm.sd_unload_bit()
        arm.sd_load_bit(driver)

    def _loosen_part(self, arm, obs, part):
        for i, f in enumerate(obs["parts"][part]["fasteners"]):
            if not f["seated"]:
                continue
            self._load_bit(arm, f["driver"])
            r = arm.sd_loosen(part, i)
            if r.ok:
                reg = arm.fm_register_removal(part, i)
                sid = reg.data["screw_id"]
                arm.fm_assign_slot(sid)
                arm.fm_place(sid)
                self._screws[(part, i)] = ("orig", sid)
            elif f["damaged"]:
                # Stripped head (inherited or otherwise): extract it and
                # quarantine it; the hole gets an exact spare at reassembly.
                arm.select_tool("screw_extractor")
                arm.extract_screw(part, i)
                reg = arm.fm_register_removal(part, i)
                sid = reg.data["screw_id"]
                arm.fm_quarantine(sid, "damaged_head")
                self._screws[(part, i)] = ("spare", None)

    def _tighten_part(self, arm, obs, part):
        for i, f in enumerate(obs["parts"][part]["fasteners"]):
            entry = self._screws.get((part, i))
            if entry and entry[0] == "spare":
                arm.fm_assign_spare(part, i, f["driver"], f["size"], f["length_mm"])
            elif f["removed"]:
                arm.fm_assign_spare(part, i, f["driver"], f["size"], f["length_mm"])
            elif entry and entry[0] == "orig":
                arm.fm_retrieve(entry[1], part, i)
            elif f["seated"] and not f["under_torqued"]:
                continue
            self._load_bit(arm, f["driver"])
            if arm.sd.torque != "spec":
                arm.sd_set_torque("spec")
            arm.sd_tighten(part, i)

    # -- cleaning -------------------------------------------------------------
    def _clean_surface(self, arm, surface):
        """Bring one surface to all-zero contamination using the matrix:
        detail/soft brush + glancing air for dust, fresh pre-moistened
        wipes for everything else. Mesh/port get no wipes (fibre shed)."""
        for _ in range(4):
            levels = arm.observe()["contamination"][surface]
            if all(v == 0 for v in levels.values()):
                return
            if levels["C1"] > 0:
                arm.cl_brush_pass(surface, "detail")
                arm.cl_air_blast(surface, "low", "glancing")
            levels = arm.observe()["contamination"][surface]
            if all(v == 0 for v in levels.values()):
                return
            if surface in ("speaker_mesh", "port_interior"):
                arm.cl_brush_pass(surface, "firm")
                continue
            r = arm.cl_dispense_wipe("premoistened")
            if not r.ok:
                return
            for _ in range(3):
                res = arm.cl_wipe(surface)
                if all(v == 0 for v in res.data["levels"].values()):
                    break
                if res.data["wipe_state"] == "loaded":
                    break
            arm.cl_dispose_wipe()

    def _final_pass(self, arm):
        """The Max final pass (cleaning spec §5.6): every exterior surface
        at all-zero, frame -> meshes/ports -> glass last, fresh wipes."""
        obs = arm.observe()
        for surface in FINAL_PASS_ORDER:
            if any(v > 0 for v in obs["contamination"][surface].values()):
                self._clean_surface(arm, surface)
        for surface in FINAL_PASS_ORDER:      # closing inspection sweep
            arm.cl_inspect_surface(surface)

    # -- procedure --------------------------------------------------------------
    def run(self, arm, job, tier):
        self._screws = {}
        arm.hd_set_protocol("edge_grip")
        if arm.fm.active_phone_id != arm.phone.phone_id:
            arm.fm_begin_phone(job.id)
        obs = arm.observe()
        if job.kind == "deep_clean":
            for surface in FINAL_PASS_ORDER:
                self._clean_surface(arm, surface)
        else:
            self._service_part(arm, obs, job.target_part, obs["cover_part"])
        self._verify_and_signoff(arm, tier)

    def _remove_fastened_part(self, arm, part):
        """Loosen (with mat custody), disconnect, and remove a bracket or
        blocker part."""
        obs = arm.observe()
        arm.select_tool("spudger")
        for c in obs["parts"][part]["connectors"]:
            arm.disconnect(c)
        self._loosen_part(arm, obs, part)
        arm.remove_part(part)

    def _reinstall_part(self, arm, part):
        arm.install_part(part)
        self._tighten_part(arm, arm.observe(), part)
        arm.select_tool("spudger")
        for c in arm.observe()["parts"][part]["connectors"]:
            arm.connect(c)

    def _service_part(self, arm, obs, target, cover):
        phone_parts = obs["parts"]
        opened_cover = False
        removed_cover = False
        brackets, blockers = [], []
        if target != cover:
            opened_cover, removed_cover = self._open_cover(arm, obs, cover)
        # Remove bracket parts hiding connectors we need.
        needed = list(phone_parts[target]["connectors"])
        if target != "battery":
            needed += list(phone_parts["battery"]["connectors"])
        for conn in needed:
            bracket = obs["covered_connectors"].get(conn)
            if bracket and bracket not in (target, cover) \
                    and arm.phone.parts[bracket].installed \
                    and bracket not in brackets:
                self._remove_fastened_part(arm, bracket)
                brackets.append(bracket)
        # Safety: disconnect the battery before internal work.
        if target != "battery":
            arm.select_tool("spudger")
            for c in phone_parts["battery"]["connectors"]:
                arm.disconnect(c)
        # Service the target.
        t = phone_parts[target]
        arm.select_tool("spudger")
        for c in t["connectors"]:
            arm.disconnect(c)
        self._loosen_part(arm, arm.observe(), target)
        part_obj = arm.phone.parts[target]
        if part_obj.adhesive:
            if target == "battery" or part_obj.condition == "swollen":
                for b in obs["adhesive_tab_blockers"].get(target, []):
                    if arm.phone.parts[b].installed:
                        self._remove_fastened_part(arm, b)
                        blockers.append(b)
                arm.select_tool("tweezers")
                arm.pull_adhesive_tabs(target)     # never heat near a battery
            else:
                arm.heat_set_temperature(80)   # mid softening band, set explicitly
                arm.select_tool("heat_plate")
                arm.soften_adhesive(target)
        arm.remove_part(target)
        arm.install_part(target, new=True)
        if part_obj.adhesive:
            arm.select_tool("adhesive_applicator")
            arm.apply_adhesive(target)
        self._tighten_part(arm, arm.observe(), target)
        arm.select_tool("spudger")
        for c in t["connectors"]:
            arm.connect(c)
        # Reconnect battery, restore blockers and brackets, close up.
        if target != "battery":
            for c in phone_parts["battery"]["connectors"]:
                arm.connect(c)
        for b in reversed(blockers):
            self._reinstall_part(arm, b)
        for b in reversed(brackets):
            arm.install_part(b)
            self._tighten_part(arm, arm.observe(), b)
        if removed_cover:
            arm.install_part(cover)
            self._tighten_part(arm, arm.observe(), cover)
            arm.select_tool("spudger")
            for c in phone_parts[cover]["connectors"]:
                arm.connect(c)
        elif opened_cover:
            arm.close_part(cover)
            self._tighten_part(arm, arm.observe(), cover)

    def _open_cover(self, arm, obs, cover):
        """Returns (opened, removed): hinged-open for devices whose
        connectors are covered (the cover's own cables stay attached
        until the brackets are off), fully removed otherwise."""
        c = obs["parts"][cover]
        self._loosen_part(arm, obs, cover)
        part_obj = arm.phone.parts[cover]
        if part_obj.adhesive:
            arm.heat_set_temperature(80)   # mid softening band, set explicitly
            arm.select_tool("heat_plate")
            arm.soften_adhesive(cover)
        if obs["covered_connectors"]:
            arm.open_part(cover)
            return True, False
        arm.select_tool("spudger")
        for conn in c["connectors"]:
            arm.disconnect(conn)
        arm.remove_part(cover)
        return False, True

    def _verify_and_signoff(self, arm, tier):
        arm.power_on()
        # Unlock + activation through the mirror (dt_) and whitelist (dg_).
        arm.dt_connect_mirror()
        arm.dt_mount_tool()
        arm.dt_swipe("swipe_up_affordance", "up")
        arm.dg_unlock_check()
        screen = arm.observe()["screen"]
        if screen and screen["screen"] == "activation_screen":
            arm.dt_tap("continue_button")
        arm.dg_activation_check()
        arm.dg_read_battery_health()
        arm.dg_run_diagnostic("post_observation")
        arm.dt_disconnect_mirror()
        if tier == "Max":
            # Charge to the Max sign-off level — unless the battery in the
            # phone is known damaged/swollen (e.g. a swollen battery that
            # was not the repair target): charging one is classifier-
            # blocked for safety, and the battery_at_50 gate then fails on
            # the spec's own terms rather than on a policy error.
            if arm.phone.battery_percent < 50 and \
                    arm.phone.battery_condition_known not in ("damaged", "swollen"):
                arm.pw_connect_cable()
                arm.pw_supply_on()
                arm.pw_charge_to(50)       # plain charge; never spans 20->80
                arm.pw_disconnect_cable()
            self._final_pass(arm)
        else:
            # A careful tech always wipes the display after reassembly:
            # handling smudges are part of the job, at every tier.
            if any(v > 0 for v in arm.observe()["contamination"]["front_glass"].values()):
                self._clean_surface(arm, "front_glass")


class SloppyPolicy:
    name = "sloppy"

    def run(self, arm, job, tier):
        obs = arm.observe()
        if job.kind == "deep_clean":
            arm.select_tool("brush")
            arm.clean("device")
            arm.power_on()
            return
        target = job.target_part
        cover = obs["cover_part"]
        parts = obs["parts"]
        arm.sd_load_bit("phillips")        # one bit for everything, left in
        if target != cover:
            for i, f in enumerate(parts[cover]["fasteners"]):
                arm.sd_loosen(cover, i)
            arm.select_tool("spudger")
            for c in parts[cover]["connectors"]:
                arm.disconnect(c)
            if arm.phone.parts[cover].adhesive:
                arm.select_tool("heat_plate")
                arm.soften_adhesive(cover)
            arm.remove_part(cover)
        # Target: no battery disconnect, no adhesive care, torque never set,
        # no mat (every screw unrecorded), no care for brackets or blockers.
        t = parts[target]
        for i, f in enumerate(t["fasteners"]):
            arm.sd_loosen(target, i)
        arm.select_tool("spudger")
        for c in t["connectors"]:
            arm.disconnect(c)
        if arm.phone.parts[target].adhesive:
            arm.select_tool("heat_plate")
            arm.soften_adhesive(target)    # heat on a battery: what could go wrong
        r = arm.remove_part(target)
        if not r.ok:
            self._loosen_all(arm, target)
            arm.remove_part(target)
        arm.install_part(target, new=True)
        for i, f in enumerate(t["fasteners"]):
            arm.sd_tighten(target, i)      # torque unset -> under-seated screws
        arm.select_tool("spudger")
        for c in t["connectors"]:
            arm.connect(c)
        if target != cover:
            arm.install_part(cover)
            for i, f in enumerate(parts[cover]["fasteners"]):
                arm.sd_tighten(cover, i)
            for c in parts[cover]["connectors"]:
                arm.connect(c)
        # Shortcuts that the gates judge, each in its own instructive way.
        arm.power_on()
        arm.run_diagnostic(standard=False)     # non-whitelisted suite (High disqualifier)
        arm.restore_device()                   # 'to be safe' (High disqualifier)
        arm.update_os()                        # (Max disqualifier)
        arm.change_setting("brightness", 1.0)  # (Max disqualifier)
        # No charge to 50, no clean: fingerprints stay (Max disqualifier).

    def _loosen_all(self, arm, part):
        obs = arm.observe()
        for i, f in enumerate(obs["parts"][part]["fasteners"]):
            if f["seated"]:
                if arm.sd.loaded_bit != f["driver"]:
                    if arm.sd.loaded_bit is not None:
                        arm.sd_unload_bit()
                    arm.sd_load_bit(f["driver"])
                arm.sd_loosen(part, i)
        arm.select_tool("spudger")
        for c in obs["parts"][part]["connectors"]:
            arm.disconnect(c)


# ---------------------------------------------------------------------------
# Manual mode: the model guides a human. The guide emits steps; a simulated
# human executor (in runner.py) carries them out with an error profile.
# ---------------------------------------------------------------------------

class GuidePolicy:
    """Produces instruction steps: [{action, part, tool, text}]. Clarity and
    safety of the guidance are what the technician reviews."""
    name = "guide"

    def instructions(self, obs, job) -> list[dict]:
        steps = []
        if job.kind == "deep_clean":
            # A real deep clean is surface-by-surface (cleaning spec): brush
            # and air for dust, fresh pre-moistened wipes for the rest,
            # meshes/ports brushed only (wipes shed fibre into them),
            # glass last.
            for surface in FINAL_PASS_ORDER:
                steps.append({"action": "cl_brush_pass", "surface": surface,
                              "brush": "detail", "tool": "brush",
                              "text": f"Detail-brush the {surface} to lift loose dust."})
                steps.append({"action": "cl_air_blast", "surface": surface,
                              "pressure": "low", "angle": "glancing",
                              "text": f"Glancing low-pressure air across the {surface}."})
                if surface in ("speaker_mesh", "port_interior"):
                    steps.append({"action": "cl_brush_pass", "surface": surface,
                                  "brush": "firm", "tool": "brush",
                                  "text": f"Firm brush pass on the {surface}; never "
                                          f"wipe it (fibre sheds into it)."})
                else:
                    steps.append({"action": "cl_dispense_wipe", "kind": "premoistened",
                                  "tool": "cleaning_cloth",
                                  "text": f"Take a fresh pre-moistened wipe for the {surface}."})
                    for _ in range(3):
                        steps.append({"action": "cl_wipe", "surface": surface,
                                      "tool": "cleaning_cloth",
                                      "text": f"Wipe the {surface}; repeat until it "
                                              f"comes away clean."})
                    steps.append({"action": "cl_dispose_wipe",
                                  "tool": "cleaning_cloth",
                                  "text": "Dispose of the wipe; never carry a loaded "
                                          "wipe to another surface."})
            steps.append({"action": "power_on",
                          "text": "Power the device on and confirm it boots."})
            return steps
        target = job.target_part
        cover = obs["cover_part"]
        parts = obs["parts"]
        covered = obs.get("covered_connectors", {})
        brackets = []
        if target != cover:
            for i, f in enumerate(parts[cover]["fasteners"]):
                if f["damaged"]:
                    steps.append({"action": "extract_screw", "part": cover, "index": i,
                                  "tool": "screw_extractor",
                                  "text": f"Screw {i+1} on the {cover} is stripped: "
                                          f"extract it with the screw extractor."})
                    continue
                steps.append({"action": "sd_loosen", "part": cover, "index": i,
                              "tool": f["driver"],
                              "text": f"Load the {f['driver']} bit and loosen {cover} "
                                      f"screw {i+1} ({f['spec']})."})
            if parts[cover].get("adhesive"):
                steps.append({"action": "soften_adhesive", "part": cover,
                              "tool": "heat_plate",
                              "text": f"Warm the {cover} edges to release its adhesive."})
            if covered:
                steps.append({"action": "open_part", "part": cover, "tool": "suction_cup",
                              "text": f"Swing the {cover} open like a book; its cables "
                                      f"stay attached for now."})
            else:
                for c in parts[cover]["connectors"]:
                    steps.append({"action": "disconnect", "connector": c, "tool": "spudger",
                                  "text": f"With the spudger, disconnect {c}."})
                steps.append({"action": "remove_part", "part": cover, "tool": "suction_cup",
                              "text": f"Lift the {cover} off and set it aside face-down."})
        # Brackets hiding connectors come off before those connectors.
        needed = list(parts[target]["connectors"])
        if target != "battery":
            needed += list(parts["battery"]["connectors"])
        for conn in needed:
            bracket = covered.get(conn)
            if bracket and bracket not in brackets and bracket != target:
                brackets.append(bracket)
                for i, f in enumerate(parts[bracket]["fasteners"]):
                    steps.append({"action": "sd_loosen", "part": bracket, "index": i,
                                  "tool": f["driver"],
                                  "text": f"Load the {f['driver']} bit and loosen {bracket} "
                                          f"screw {i+1} ({f['spec']}). Keep these screws "
                                          f"in order on the mat: their lengths differ."})
                steps.append({"action": "remove_part", "part": bracket, "tool": "tweezers",
                              "text": f"Slide the {bracket} clear of the flex cables "
                                      f"and lift it out."})
        for c in parts["battery"]["connectors"]:
            if target != "battery":
                steps.append({"action": "disconnect", "connector": c, "tool": "spudger",
                              "text": f"Disconnect the battery connector {c} before "
                                      f"touching anything else."})
        for i, f in enumerate(parts[target]["fasteners"]):
            if f["damaged"]:
                steps.append({"action": "extract_screw", "part": target, "index": i,
                              "tool": "screw_extractor",
                              "text": f"Screw {i+1} on the {target} is stripped: "
                                      f"extract it with the screw extractor."})
                continue
            steps.append({"action": "sd_loosen", "part": target, "index": i,
                          "tool": f["driver"],
                          "text": f"Load the {f['driver']} bit and loosen {target} "
                                  f"screw {i+1} ({f['spec']}). Keep screws in order."})
        for c in parts[target]["connectors"]:
            steps.append({"action": "disconnect", "connector": c, "tool": "spudger",
                          "text": f"Disconnect {c} with the spudger."})
        blockers = []
        if parts[target].get("adhesive"):
            if target == "battery":
                for b in obs.get("adhesive_tab_blockers", {}).get(target, []):
                    if parts[b]["installed"]:
                        blockers.append(b)
                        for c in parts[b]["connectors"]:
                            steps.append({"action": "disconnect", "connector": c,
                                          "tool": "spudger",
                                          "text": f"Disconnect {c}."})
                        for i, f in enumerate(parts[b]["fasteners"]):
                            steps.append({"action": "sd_loosen", "part": b, "index": i,
                                          "tool": f["driver"],
                                          "text": f"Loosen {b} screw {i+1} ({f['spec']})."})
                        steps.append({"action": "remove_part", "part": b, "tool": "tweezers",
                                      "text": f"Remove the {b}; it blocks the battery "
                                              f"pull tabs."})
                steps.append({"action": "pull_adhesive_tabs", "part": target,
                              "tool": "tweezers",
                              "text": "Pull the battery adhesive tabs slowly; never "
                                      "apply heat to a battery."})
            else:
                steps.append({"action": "soften_adhesive", "part": target,
                              "tool": "heat_plate",
                              "text": f"Warm the {target} edges on the heat plate to "
                                      f"release the adhesive."})
        steps.append({"action": "remove_part", "part": target, "tool": "tweezers",
                      "text": f"Remove the faulty {target}."})
        steps.append({"action": "install_part", "part": target, "new": True,
                      "tool": "tweezers",
                      "text": f"Seat the replacement {target}."})
        for i, f in enumerate(parts[target]["fasteners"]):
            if f["damaged"]:
                steps.append({"action": "replace_screw", "part": target, "index": i,
                              "tool": "tweezers",
                              "text": f"Drop a fresh spare screw into {target} "
                                      f"hole {i+1} (the stripped one was extracted)."})
            steps.append({"action": "sd_tighten", "part": target, "index": i,
                          "tool": f["driver"], "torque": "spec",
                          "text": f"Load the {f['driver']} bit, set torque to spec, and "
                                  f"tighten {target} screw {i+1}."})
        for c in parts[target]["connectors"]:
            steps.append({"action": "connect", "connector": c, "tool": "spudger",
                          "text": f"Reconnect {c}; it should click softly."})
        if target != "battery":
            for c in parts["battery"]["connectors"]:
                steps.append({"action": "connect", "connector": c, "tool": "spudger",
                              "text": f"Reconnect the battery connector {c}."})
        for b in reversed(blockers):
            steps.append({"action": "install_part", "part": b, "tool": "tweezers",
                          "text": f"Reinstall the {b}."})
            for i, f in enumerate(parts[b]["fasteners"]):
                steps.append({"action": "sd_tighten", "part": b, "index": i,
                              "tool": f["driver"], "torque": "spec",
                              "text": f"Tighten {b} screw {i+1} ({f['spec']}) at spec torque."})
            for c in parts[b]["connectors"]:
                steps.append({"action": "connect", "connector": c, "tool": "spudger",
                              "text": f"Reconnect {c}."})
        for b in reversed(brackets):
            steps.append({"action": "install_part", "part": b, "tool": "tweezers",
                          "text": f"Reinstall the {b} over the connectors."})
            for i, f in enumerate(parts[b]["fasteners"]):
                steps.append({"action": "sd_tighten", "part": b, "index": i,
                              "tool": f["driver"], "torque": "spec",
                              "text": f"Tighten {b} screw {i+1} ({f['spec']}) at spec "
                                      f"torque, in its own hole."})
        if target != cover:
            if covered:
                steps.append({"action": "close_part", "part": cover, "tool": "suction_cup",
                              "text": f"Close the {cover} and press it home."})
            else:
                steps.append({"action": "install_part", "part": cover, "tool": "suction_cup",
                              "text": f"Reinstall the {cover}."})
            for i, f in enumerate(parts[cover]["fasteners"]):
                if f["damaged"] and not covered:
                    steps.append({"action": "replace_screw", "part": cover, "index": i,
                                  "tool": "tweezers",
                                  "text": f"Drop a fresh spare screw into {cover} "
                                          f"hole {i+1} (the stripped one was extracted)."})
                steps.append({"action": "sd_tighten", "part": cover, "index": i,
                              "tool": f["driver"], "torque": "spec",
                              "text": f"Tighten {cover} screw {i+1} ({f['spec']}) at spec torque."})
            if not covered:
                for c in parts[cover]["connectors"]:
                    steps.append({"action": "connect", "connector": c, "tool": "spudger",
                                  "text": f"Reconnect {c}."})
        steps.append({"action": "power_on", "text": "Power on and confirm the device boots."})
        steps.append({"action": "run_diagnostic", "standard": True, "tool": "diagnostic_rig",
                      "text": "Run the standard diagnostic suite only."})
        return steps
