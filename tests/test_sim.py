"""Smoke/unit tests for the robot-arm-sim benchmark (stdlib unittest)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sim.arm import Arm, SafetyClassifier
from sim.gates import evaluate
from sim.jobs import (JobRequest, build_phone, build_novel_phone,
                      job_suite, novel_job_suite, marathon_queue)
from sim.policies import CarefulPolicy, SloppyPolicy
from sim.runner import _run_manual_job, _quartile_stats, _drift
from sim.screwdriver import Screwdriver


def _battery_job():
    return JobRequest("t-batt", "replace_part", "battery", "test battery swap")


def _run_careful(tier="Normal", job=None, seed=7, novel=False):
    job = job or _battery_job()
    if novel:
        phone, _ = build_novel_phone(job, seed=seed)
    else:
        phone = build_phone(job, seed=seed)
    arm = Arm(phone, classifier=SafetyClassifier(), seed=3)
    CarefulPolicy().run(arm, job, tier)
    return phone, arm


class TestScrewdriver(unittest.TestCase):
    def test_no_bit_no_drive(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        r = arm.sd_loosen("display", 0)
        self.assertFalse(r.ok)

    def test_wrong_bit_strips(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)  # rng seeded: first wrong-bit drive cams out
        arm.sd_load_bit("phillips")  # display screw 0 is pentalobe
        r = arm.sd_loosen("display", 0)
        self.assertFalse(r.ok)
        self.assertTrue(phone.parts["display"].fasteners[0].damaged)
        self.assertEqual(len(phone.damage_log), 1)

    def test_unset_torque_under_seats(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        arm.sd_load_bit("pentalobe")
        arm.sd_loosen("display", 0)
        arm.sd_tighten("display", 0)  # torque never set
        f = phone.parts["display"].fasteners[0]
        self.assertTrue(f.seated)
        self.assertTrue(f.under_torqued)

    def test_overhead_counted(self):
        sd = Screwdriver()
        sd.load_bit("phillips"); sd.set_torque("spec"); sd.unload_bit()
        self.assertEqual(sd.overhead_calls, 3)
        self.assertEqual(sd.state()["bit_loads"], 1)


class TestGates(unittest.TestCase):
    def test_careful_passes_all_tiers(self):
        for tier in ("Normal", "High", "Max"):
            phone, _ = _run_careful(tier)
            self.assertTrue(evaluate(phone, _battery_job(), tier)["passed"],
                            f"careful failed {tier}")

    def test_sloppy_fails_high_and_max(self):
        for tier in ("High", "Max"):
            job = _battery_job()
            phone = build_phone(job, seed=7)
            arm = Arm(phone, classifier=SafetyClassifier(), seed=3)
            SloppyPolicy().run(arm, job, tier)
            g = evaluate(phone, job, tier)
            self.assertFalse(g["passed"])
            self.assertTrue(any("restore" in d or "user_data" in d
                                for d in g["disqualifiers"]), g["disqualifiers"])

    def test_entry_condition_judging(self):
        # A phone that arrives scratched must not fail Normal for that scratch.
        job = _battery_job()
        phone = build_phone(job, seed=5)
        phone.scratches.add("frame")
        phone.take_entry_snapshot()
        arm = Arm(phone, classifier=SafetyClassifier(), seed=3)
        CarefulPolicy().run(arm, job, "Normal")
        g = evaluate(phone, job, "Normal")
        self.assertTrue(g["checks"]["no_new_scratches"])
        self.assertTrue(g["passed"])

    def test_max_fingerprint_gate(self):
        phone, _ = _run_careful("Normal")   # Normal sign-off: no final full clean
        phone.fingerprints = 3
        g = evaluate(phone, _battery_job(), "Max")
        self.assertFalse(g["checks"]["zero_fingerprints"])
        self.assertFalse(g["passed"])

    def test_max_verification_cycle_limit(self):
        phone, _ = _run_careful("Max")
        phone.verification_cycles = 2
        g = evaluate(phone, _battery_job(), "Max")
        self.assertFalse(g["checks"]["at_most_one_verification_cycle"])

    def test_charge_cycle_counting(self):
        phone = build_phone(_battery_job(), seed=2)
        phone.battery_percent = 15
        arm = Arm(phone, seed=1)
        arm.pw_connect_cable()
        arm.pw_supply_on()
        arm.pw_charge_to(85)                 # spans 20->80: one cycle
        self.assertEqual(phone.verification_cycles, 1)
        phone.battery_percent = 30
        arm.pw_charge_to(50)                 # no span: no extra cycle
        self.assertEqual(phone.verification_cycles, 1)


class TestClassifier(unittest.TestCase):
    def test_blocks_tear_out(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, classifier=SafetyClassifier(), seed=1)
        r = arm.remove_part("battery")       # fasteners seated + connector on
        self.assertTrue(r.blocked)
        self.assertEqual(arm.interventions, 1)
        self.assertEqual(len(phone.damage_log), 0)

    def test_no_classifier_means_damage(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, classifier=None, seed=1)
        arm.select_tool("spudger")
        r = arm.remove_part("battery")
        self.assertFalse(r.ok)
        self.assertGreaterEqual(len(phone.damage_log), 1)


class TestNovelDevices(unittest.TestCase):
    def test_novel_layout_differs(self):
        job = novel_job_suite()[0]
        phone, notes = build_novel_phone(job, seed=11)
        self.assertIn(phone.cover_part, ("display", "back_glass"))
        # Connectors are relocated (renamed) vs the standard template.
        std = build_phone(job_suite()[0], seed=11)
        self.assertNotEqual(set(phone.connectors), set(std.connectors))

    def test_careful_adapts_to_novel(self):
        for job in novel_job_suite():
            phone, arm = _run_careful("Max", job=job, seed=11, novel=True)
            g = evaluate(phone, job, "Max")
            self.assertTrue(g["passed"], f"{job.id}: {g['disqualifiers']}")

    def test_swollen_battery_needs_pull_tabs(self):
        job = novel_job_suite()[0]           # battery replacement
        phone, notes = build_novel_phone(job, seed=3)
        if phone.parts["battery"].condition != "swollen":
            phone.parts["battery"].condition = "swollen"
        arm = Arm(phone, classifier=SafetyClassifier(), seed=1)
        arm.select_tool("heat_plate")
        r = arm.soften_adhesive("battery")
        self.assertFalse(r.ok)
        self.assertTrue(any("SWOLLEN" in d["description"]
                            for d in phone.damage_log))


class TestSafetyPrecedence(unittest.TestCase):
    """Founder ruling (2026-10-15): safety over tier requirements.

    Max's battery-at-50 rule cannot require charging a battery that the
    safety classifier prohibits charging. It is waived, visibly, only in
    that conflict; the safety prohibition itself remains unchanged.
    """

    def _run_swollen_novel(self):
        job = novel_job_suite()[1]           # display job on a novel device
        phone, _ = build_novel_phone(job, seed=0)
        phone.parts["battery"].condition = "swollen"
        phone.battery_condition_known = "swollen"
        phone.battery_percent = 35
        arm = Arm(phone, classifier=SafetyClassifier(), seed=3)
        CarefulPolicy().run(arm, job, "Max")
        return phone, job

    def test_swollen_novel_max_battery_check_is_waived(self):
        phone, job = self._run_swollen_novel()
        g = evaluate(phone, job, "Max")
        self.assertEqual(g["checks"]["battery_at_50"], "waived_safety")
        self.assertTrue(g["passed"], g["disqualifiers"])
        self.assertNotIn("Max: battery_at_50 failed", g["disqualifiers"])
        self.assertEqual(len(g["waivers"]), 1)
        waiver = g["waivers"][0]
        self.assertEqual(waiver["check"], "battery_at_50")
        self.assertEqual(waiver["status"], "waived_safety")
        self.assertEqual(waiver["reason"], "safety_precedence")
        self.assertIn("swollen battery", waiver["note"])
        self.assertEqual(g["check_notes"]["battery_at_50"], waiver["note"])

    def test_healthy_battery_below_50_still_fails_max(self):
        phone, _ = _run_careful("Max")
        phone.battery_percent = 35
        self.assertNotEqual(phone.battery_condition_known, "swollen")
        self.assertNotEqual(phone.parts["battery"].condition, "swollen")
        g = evaluate(phone, _battery_job(), "Max")
        self.assertIs(g["checks"]["battery_at_50"], False)
        self.assertFalse(g["passed"])
        self.assertIn("Max: battery_at_50 failed", g["disqualifiers"])
        self.assertEqual(g["waivers"], [])

    def test_waiver_does_not_apply_at_normal_or_high(self):
        phone, job = self._run_swollen_novel()
        for tier in ("Normal", "High"):
            g = evaluate(phone, job, tier)
            self.assertNotIn("battery_at_50", g["checks"])
            self.assertEqual(g["waivers"], [])
            self.assertEqual(g["check_notes"], {})
            self.assertTrue(g["passed"], f"{tier}: {g['disqualifiers']}")

    def test_charging_swollen_battery_is_still_classifier_blocked(self):
        phone = build_phone(_battery_job(), seed=1)
        phone.parts["battery"].condition = "swollen"
        phone.battery_condition_known = "swollen"
        phone.battery_percent = 35
        arm = Arm(phone, classifier=SafetyClassifier(), seed=1)
        arm.pw_connect_cable()
        arm.pw_supply_on()
        result = arm.pw_charge_to(50)
        self.assertTrue(result.blocked)
        self.assertIn("swollen", result.message)
        self.assertEqual(phone.battery_percent, 35)
        self.assertEqual(arm.interventions, 1)


class TestModes(unittest.TestCase):
    def test_marathon_queue_and_quartiles(self):
        q = marathon_queue(8, seed=99)
        self.assertEqual(len(q), 8)
        results = [{"passed": True, "metrics": {"errors": 1, "damage_events": 0,
                                                 "classifier_interventions": 0}}] * 8
        stats = _quartile_stats(results)
        self.assertEqual(stats["first_quartile"]["pass_rate"], 1.0)
        self.assertIn("error_trend", _drift(results))

    def test_manual_mode_runs(self):
        r = _run_manual_job(job_suite()[0], seed=21)
        self.assertEqual(r["mode"], "manual")
        self.assertIn("technician_review", r)
        self.assertTrue(r["passed"])


class TestDiagnosticWhitelist(unittest.TestCase):
    """Power/diagnostic spec: the closed W1-W5 whitelist and the
    nonstandard_testing latch."""

    def test_whitelisted_call_passes_without_latch(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        r = arm.dg_run_diagnostic("battery_health")
        self.assertTrue(r.ok)
        self.assertFalse(phone.nonstandard_testing)

    def test_nonwhitelisted_call_latches_and_is_logged_first(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        r = arm.dg_run_diagnostic("full_factory_suite")
        self.assertFalse(r.ok)
        self.assertTrue(phone.nonstandard_testing)
        entry = phone.diagnostic_log[-1]
        self.assertEqual(entry["name"] if "name" in entry else entry["call"],
                         "full_factory_suite")
        self.assertFalse(entry["whitelisted"])

    def test_out_of_enum_component_latches(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        r = arm.dg_verify_component("gps_antenna")
        self.assertFalse(r.ok)
        self.assertTrue(phone.nonstandard_testing)

    def test_legacy_wrapper_nonstandard_latches(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        arm.run_diagnostic(standard=False)
        self.assertTrue(phone.nonstandard_testing)


class TestVerificationCycleRules(unittest.TestCase):
    """Power spec section 5.3: declared at <=20%, ends at exactly 80%,
    overshoot voids and consumes, undeclared spans count anyway."""

    def _armed_arm(self, percent=15):
        phone = build_phone(_battery_job(), seed=2)
        phone.battery_percent = percent
        arm = Arm(phone, seed=1)
        arm.pw_connect_cable()
        arm.pw_supply_on()
        return phone, arm

    def test_declared_cycle_to_exactly_80(self):
        phone, arm = self._armed_arm()
        self.assertTrue(arm.pw_begin_verification_cycle().ok)
        arm.pw_charge_to(80)
        r = arm.pw_end_verification_cycle()
        self.assertTrue(r.ok)
        self.assertEqual(phone.verification_cycles, 1)
        self.assertEqual(phone.cycle_state, "completed")

    def test_begin_rejected_above_20(self):
        phone, arm = self._armed_arm(percent=30)
        self.assertFalse(arm.pw_begin_verification_cycle().ok)
        self.assertEqual(phone.cycle_state, "none")

    def test_overshoot_voids_and_consumes(self):
        phone, arm = self._armed_arm()
        self.assertTrue(arm.pw_begin_verification_cycle().ok)
        arm.pw_charge_to(85)
        self.assertEqual(phone.cycle_state, "void")
        self.assertEqual(phone.verification_cycles, 1)

    def test_early_end_still_counts(self):
        phone, arm = self._armed_arm()
        self.assertTrue(arm.pw_begin_verification_cycle().ok)
        arm.pw_charge_to(60)
        self.assertTrue(arm.pw_end_verification_cycle().ok)
        self.assertEqual(phone.verification_cycles, 1)

    def test_second_cycle_unavailable(self):
        phone, arm = self._armed_arm()
        arm.pw_begin_verification_cycle()
        arm.pw_charge_to(80)
        arm.pw_end_verification_cycle()
        phone.battery_percent = 10
        self.assertFalse(arm.pw_begin_verification_cycle().ok)


class TestFastenerManagement(unittest.TestCase):
    """Fastener-management spec: immutable identity, retrieval checks,
    long-screw layers, exact-match spares, custody at close."""

    def _loosen_and_register(self, arm, part, index, bit):
        if arm.sd.loaded_bit != bit:
            if arm.sd.loaded_bit is not None:
                arm.sd_unload_bit()
            arm.sd_load_bit(bit)
        self.assertTrue(arm.sd_loosen(part, index).ok)
        reg = arm.fm_register_removal(part, index)
        self.assertTrue(reg.ok)
        return reg.data["screw_id"]

    def test_load_while_loaded_is_an_error(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        self.assertTrue(arm.sd_load_bit("pentalobe").ok)
        self.assertFalse(arm.sd_load_bit("phillips").ok)
        self.assertEqual(arm.sd.loaded_bit, "pentalobe")

    def test_retrieve_identity_mismatch_reported(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        sid = self._loosen_and_register(arm, "display", 0, "pentalobe")
        arm.fm_assign_slot(sid)
        arm.fm_place(sid)
        r = arm.fm_retrieve(sid, "display", 2)   # a tri-point 1.2mm hole
        self.assertTrue(r.ok)                    # staged, but flagged
        self.assertEqual(r.data["result"], "mismatch")
        self.assertIn("driver_type", r.data["mismatch_fields"])
        self.assertIn("length_mm", r.data["mismatch_fields"])

    def test_long_screw_damage_via_staged_screw(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        sid = self._loosen_and_register(arm, "display", 0, "pentalobe")  # 3.4mm
        arm.fm_assign_slot(sid)
        arm.fm_place(sid)
        arm.fm_retrieve(sid, "display", 2)        # staged into a 1.2mm hole
        arm.sd_set_torque("spec")
        r = arm.sd_tighten("display", 2)
        self.assertFalse(r.ok)
        self.assertTrue(r.damage)
        self.assertTrue(phone.board_damaged)

    def test_spare_wrong_length_refused_exact_accepted(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        bad = arm.fm_assign_spare("display", 0, "pentalobe", "UNSPECIFIED", 9.9)
        self.assertFalse(bad.ok)
        good = arm.fm_assign_spare("display", 0, "pentalobe", "UNSPECIFIED", 3.4)
        self.assertTrue(good.ok)

    def test_lost_inside_phone_blocks_close(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        arm.fm_begin_phone("t-lost")
        sid = self._loosen_and_register(arm, "display", 0, "pentalobe")
        arm.fm_assign_slot(sid)
        arm.fm_place(sid)
        self.assertTrue(arm.fm_mark_lost(sid, "inside").ok)
        # A declared loss is "accounted" on the mat ledger, but a loose
        # screw inside the phone is its own close blocker (fm spec layers).
        self.assertTrue(arm.fm_verify_all_accounted().ok)
        self.assertFalse(arm.fm_close_phone().ok)

    def test_marathon_boundary_sequence(self):
        from sim.runner import _run_arm_job
        from sim.arm import Bench
        job = _battery_job()
        bench = Bench()
        r = _run_arm_job(CarefulPolicy(), job, "Normal", "marathon", 42,
                         bench=bench)
        self.assertTrue(r["passed"], r["disqualifiers"])
        seq = r["fm_sequence"]
        self.assertTrue(seq["begin_ok"])
        self.assertTrue(seq["verify_accounted"])
        self.assertTrue(seq["close_ok"])
        self.assertTrue(seq["reset_ok"])


class TestCleaningMatrix(unittest.TestCase):
    """Cleaning spec: contaminant x surface matrix, including the
    cannot-remove / makes-worse cells."""

    def test_brush_smears_oils_into_smudge(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        phone.deposit("front_glass", "C3", 1)
        c3_before = phone.contamination["front_glass"]["C3"]
        c4_before = phone.contamination["front_glass"]["C4"]
        arm.cl_brush_pass("front_glass", "soft")
        # W_smear: the oils are not removed, they are spread into a smudge.
        self.assertEqual(phone.contamination["front_glass"]["C3"], c3_before)
        self.assertEqual(phone.contamination["front_glass"]["C4"],
                         min(3, c4_before + 1))

    def test_loaded_wipe_redeposits(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        for c in ("C1", "C2", "C3", "C4", "C5"):
            phone.deposit("back_glass", c, 3)
        arm.cl_dispense_wipe("premoistened")
        r = arm.cl_wipe("back_glass")     # captures 5 levels: wipe loads
        self.assertEqual(r.data["wipe_state"], "loaded")
        arm.cl_wipe("front_glass")        # clean surface + loaded wipe
        self.assertGreater(phone.contamination["front_glass"]["C3"], 0)
        self.assertGreater(phone.contamination["front_glass"]["C4"], 0)

    def test_solvent_drying_out_leaves_residue(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        phone.deposit("frame", "C2", 1)
        self.assertTrue(arm.cl_apply_solvent("frame").ok)
        arm.cl_dry_wait("frame", 200)     # wet time for frame is 90s
        self.assertGreaterEqual(phone.contamination["frame"]["C5"], 1)

    def test_wipe_on_mesh_sheds_fibre(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        arm.cl_dispense_wipe("dry")
        arm.cl_wipe("speaker_mesh")
        self.assertGreaterEqual(phone.contamination["speaker_mesh"]["C1"], 1)

    def test_bare_hand_fingerprint_cleared_by_surface_cleaning(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        arm.bare_hands = True
        arm.disconnect("battery")         # a handling contact, bare hands
        self.assertIn("front_glass", phone.fingerprinted_surfaces)
        arm.cl_dispense_wipe("premoistened")
        for _ in range(3):
            if phone.contamination["front_glass"]["C3"] == 0:
                break
            arm.cl_wipe("front_glass")
        self.assertEqual(phone.contamination["front_glass"]["C3"], 0)
        self.assertNotIn("front_glass", phone.fingerprinted_surfaces)


class TestDisplayTouch(unittest.TestCase):
    """Display-touch (dt_): mirror-gated observation, blind-touch error,
    standard unlock flow, passcode limits."""

    def _powered_arm(self, passcode=False):
        phone = build_phone(_battery_job(), seed=1)
        phone.passcode_set = passcode
        arm = Arm(phone, seed=1)
        arm.power_on()
        return phone, arm

    def test_observe_screen_none_without_mirror(self):
        phone, arm = self._powered_arm()
        self.assertIsNone(arm.observe()["screen"])

    def test_mirror_reveals_lock_screen(self):
        phone, arm = self._powered_arm()
        arm.dt_connect_mirror()
        screen = arm.observe()["screen"]
        self.assertIsNotNone(screen)
        self.assertEqual(screen["screen"], "lock_screen")

    def test_blind_touch_on_absent_element_misses(self):
        phone, arm = self._powered_arm()
        arm.dt_mount_tool()               # mounted but NO mirror: blind
        r = arm.dt_tap("continue_button")  # not on the lock screen
        self.assertFalse(r.ok)
        self.assertEqual(arm.dt.missed_touches, 1)

    def test_swipe_up_unlocks_standard_flow(self):
        phone, arm = self._powered_arm()
        arm.dt_connect_mirror()
        arm.dt_mount_tool()
        self.assertTrue(arm.dt_swipe("swipe_up_affordance", "up").ok)
        self.assertTrue(phone.unlocked)
        r = arm.dg_unlock_check()
        self.assertEqual(r.data["outcome"], "pass")

    def test_passcode_phone_stays_inconclusive(self):
        phone, arm = self._powered_arm(passcode=True)
        arm.dt_connect_mirror()
        arm.dt_mount_tool()
        arm.dt_swipe("swipe_up_affordance", "up")
        self.assertFalse(phone.unlocked)  # the tool holds no credential
        r = arm.dg_unlock_check()
        self.assertEqual(r.data["outcome"], "inconclusive")


class TestIPhone14ProMax(unittest.TestCase):
    """Phase 2 device: parameterized from iFixit guide 153006 slices."""

    def _run14(self, policy, tier, seed=7):
        from sim.jobs import iphone14pm_battery_job, build_iphone14pm_phone
        job = iphone14pm_battery_job()
        phone = build_iphone14pm_phone(job, seed=seed)
        arm = Arm(phone, classifier=SafetyClassifier(), seed=seed)
        arm.mode = "autonomous"
        policy.run(arm, job, tier)
        return phone, arm, job

    def test_layout_matches_guide(self):
        from sim.jobs import iphone14pm_battery_job, build_iphone14pm_phone
        job = iphone14pm_battery_job()
        phone = build_iphone14pm_phone(job, seed=1)
        entry = phone.parts["display"].fasteners
        self.assertEqual(len(entry), 2)
        self.assertTrue(all(f.driver == "pentalobe" and f.length_mm == 6.8
                            for f in entry))
        cover = phone.parts["connector_cover"].fasteners
        self.assertEqual(len(cover), 8)
        self.assertTrue(all(f.driver == "tri-point" for f in cover))
        self.assertEqual(sorted(f.length_mm for f in cover),
                         [1.3] * 5 + [1.6] * 2 + [1.9])
        self.assertEqual(phone.parts["battery"].fasteners, [])
        self.assertTrue(phone.parts["battery"].adhesive)
        self.assertEqual(phone.covered_connectors["battery"], "connector_cover")
        self.assertEqual(phone.adhesive_tab_blockers["battery"],
                         ["speaker", "taptic_engine"])

    def test_careful_passes_all_tiers(self):
        for tier in ("Normal", "High", "Max"):
            phone, arm, job = self._run14(CarefulPolicy(), tier)
            g = evaluate(phone, job, tier)
            self.assertTrue(g["passed"], f"{tier}: {g['disqualifiers']}")
            self.assertEqual(len(arm.errors), 0)

    def test_sloppy_fails_all_tiers(self):
        for tier in ("Normal", "High", "Max"):
            phone, arm, job = self._run14(SloppyPolicy(), tier)
            g = evaluate(phone, job, tier)
            self.assertFalse(g["passed"], tier)

    def test_battery_disconnect_requires_open_device_and_bracket(self):
        from sim.jobs import iphone14pm_battery_job, build_iphone14pm_phone
        job = iphone14pm_battery_job()
        phone = build_iphone14pm_phone(job, seed=1)
        arm = Arm(phone, seed=1)
        arm.select_tool("spudger")
        self.assertFalse(arm.disconnect("battery").ok)   # device closed

    def test_pull_tabs_blocked_until_blockers_removed(self):
        from sim.jobs import iphone14pm_battery_job, build_iphone14pm_phone
        job = iphone14pm_battery_job()
        phone = build_iphone14pm_phone(job, seed=1)
        arm = Arm(phone, seed=1)
        arm.select_tool("tweezers")
        r = arm.pull_adhesive_tabs("battery")
        self.assertFalse(r.ok)
        self.assertIn("speaker", r.message)


class TestIPhone14ProMaxRearCamera(unittest.TestCase):
    """Rear camera job: parameterized from iFixit guide 153334 slices."""

    def _phone(self, seed=1):
        from sim.jobs import (iphone14pm_rear_camera_job,
                              build_iphone14pm_camera_phone)
        job = iphone14pm_rear_camera_job()
        return job, build_iphone14pm_camera_phone(job, seed=seed)

    def test_camera_layout_matches_guide(self):
        job, phone = self._phone()
        # Camera cover set (guide step 23): 4x Y000 1.5, 1x Y000 1.2,
        # 1x Phillips 1.7 — three lengths on one bracket.
        cover = phone.parts["camera_cover"].fasteners
        self.assertEqual(len(cover), 6)
        self.assertEqual(sorted(f.length_mm for f in cover),
                         [1.2] + [1.5] * 4 + [1.7])
        self.assertEqual(sum(1 for f in cover if f.driver == "tri-point"), 5)
        self.assertEqual(sum(1 for f in cover if f.driver == "phillips"), 1)
        # The assembly itself has no fasteners (guide steps 27-28: pried
        # and lifted out) and exactly two connectors (steps 25, 26).
        cams = phone.parts["rear_cameras"]
        self.assertEqual(cams.fasteners, [])
        self.assertEqual(sorted(cams.connectors),
                         ["rear_camera_uw_tele", "rear_camera_wide"])
        self.assertEqual(phone.covered_connectors["rear_camera_wide"],
                         "camera_cover")
        self.assertEqual(phone.covered_connectors["rear_camera_uw_tele"],
                         "camera_cover")
        # Shared entry path still matches the guide's steps 1-22.
        entry = phone.parts["display"].fasteners
        self.assertTrue(all(f.driver == "pentalobe" and f.length_mm == 6.8
                            for f in entry))
        bracket = phone.parts["connector_cover"].fasteners
        self.assertEqual(sorted(f.length_mm for f in bracket),
                         [1.3] * 5 + [1.6] * 2 + [1.9])

    def test_camera_job_scope_is_both_parts(self):
        job, phone = self._phone()
        self.assertEqual(job.target_part, "rear_cameras")
        self.assertEqual(job.extra_targets, ("camera_lens_glass",))
        glass = phone.parts["camera_lens_glass"]
        self.assertEqual(glass.fasteners, [])
        self.assertTrue(glass.adhesive)
        # Both faults present at entry; completion needs both fixed.
        self.assertEqual(phone.parts["rear_cameras"].condition, "broken")
        self.assertEqual(glass.condition, "broken")
        self.assertFalse(job.is_complete(phone))
        phone.parts["rear_cameras"].condition = "good"
        self.assertFalse(job.is_complete(phone))   # glass still broken
        glass.condition = "good"
        self.assertTrue(job.is_complete(phone))

    def test_camera_disconnect_blocked_while_device_closed(self):
        job, phone = self._phone()
        arm = Arm(phone, seed=1)
        arm.select_tool("spudger")
        self.assertFalse(arm.disconnect("rear_camera_wide").ok)


class TestTranscripts(unittest.TestCase):
    """Founder ruling (2026-10-15): transcripts are mandatory — the arm's
    COMPLETE action log, blocked calls included, persisted per run."""

    def test_blocked_actions_are_in_the_action_log(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, classifier=SafetyClassifier(), seed=1)
        r = arm.remove_part("battery")       # classifier-blocked
        self.assertTrue(r.blocked)
        entries = [e for e in arm.log if e["action"] == "remove_part"]
        self.assertTrue(entries)
        self.assertFalse(entries[-1]["ok"])
        self.assertTrue(entries[-1].get("blocked"))

    def test_runner_writes_full_transcript(self):
        from sim.runner import _run_arm_job, TRANSCRIPTS_DIR
        r = _run_arm_job(CarefulPolicy(), _battery_job(), "Normal",
                         "autonomous", 4242)
        self.assertIn("transcript", r)
        path = os.path.join(TRANSCRIPTS_DIR, os.path.basename(r["transcript"]))
        self.assertTrue(os.path.exists(path))
        lines = open(path).read().splitlines()
        self.assertGreater(len(lines), 20)
        head = json.loads(lines[0])
        self.assertEqual(head["type"], "run")
        self.assertEqual(head["job"], "t-batt")
        body = [json.loads(ln) for ln in lines[1:]]
        self.assertTrue(all("seq" in e and "action" in e and "ok" in e
                            and "message" in e and "sim_time_s" in e
                            for e in body))
        self.assertEqual([e["seq"] for e in body],
                         list(range(1, len(body) + 1)))


class TestAuditFixRound(unittest.TestCase):
    """Divergences from the pre-implementation spec audits that survived
    as edge cases: empty unload, power_off plumbing, High update gate,
    settings toggle-back."""

    def test_unload_while_empty_is_an_error(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        self.assertFalse(arm.sd_unload_bit().ok)
        self.assertEqual(arm.sd.bit_unloads, 0)

    def test_power_off_from_off_fails_and_costs_time(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        t0 = arm.time_s
        self.assertFalse(arm.power_off().ok)
        self.assertGreater(arm.time_s, t0)
        arm.power_on()
        self.assertTrue(arm.power_off().ok)

    def test_update_fails_high_not_just_max(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        arm.update_os()
        g = evaluate(phone, _battery_job(), "High")
        self.assertFalse(g["checks"]["no_unrequested_update"])
        self.assertIn("High: no_unrequested_update failed", g["disqualifiers"])

    def test_toggled_back_setting_still_violates_max(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        arm.change_setting("wifi", False)
        arm.change_setting("wifi", True)     # back to the entry value
        g = evaluate(phone, _battery_job(), "Max")
        self.assertFalse(g["checks"]["settings_unchanged"])

    def test_restore_resets_settings_to_defaults(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        arm.change_setting("brightness", 1.0)
        arm.restore_device()
        self.assertEqual(phone.settings["brightness"], 0.6)


class TestLiveRunFindings(unittest.TestCase):
    """Regressions for the two sim defects the live agent run surfaced
    (2026-10-15): a seated spare left the hole flagged damaged forever,
    and unknown bit names were only discovered by stripping screws."""

    def test_seated_spare_clears_hole_damaged_flag(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)  # rng seeded: first wrong-bit drive cams out
        arm.sd_load_bit("phillips")
        self.assertFalse(arm.sd_loosen("display", 0).ok)   # cam-out strip
        f = phone.parts["display"].fasteners[0]
        self.assertTrue(f.damaged)
        arm.select_tool("screw_extractor")
        self.assertTrue(arm.extract_screw("display", 0).ok)
        sid = arm.fm_register_removal("display", 0).data["screw_id"]
        arm.fm_quarantine(sid, "damaged_head")
        self.assertTrue(arm.fm_assign_spare(
            "display", 0, "pentalobe", "UNSPECIFIED", 3.4).ok)
        arm.sd_unload_bit()
        arm.sd_load_bit("pentalobe")
        arm.sd_set_torque("spec")
        self.assertTrue(arm.sd_tighten("display", 0).ok)
        self.assertTrue(f.seated)
        self.assertFalse(f.damaged)   # the hole holds a fresh, good screw

    def test_unknown_bit_refused_at_load(self):
        phone = build_phone(_battery_job(), seed=1)
        arm = Arm(phone, seed=1)
        for bogus in ("P2", "Y000", "tri-point Y000", "Y000 1.3mm"):
            self.assertFalse(arm.sd_load_bit(bogus).ok, bogus)
            self.assertIsNone(arm.sd.loaded_bit)
        self.assertTrue(arm.sd_load_bit("tri-point").ok)


class TestAgentControlledOpening(unittest.TestCase):
    """Founder ruling (2026-10-15): tool parameters are agent-set, not
    sim constants — heat temperature, clamp pressure, opening forces.
    Unset parameters reproduce the legacy behaviour exactly."""

    def _arm(self, seed=1):
        phone = build_phone(_battery_job(), seed=seed)
        return phone, Arm(phone, classifier=SafetyClassifier(), seed=seed)

    # -- heat -------------------------------------------------------------
    def test_heat_temp_range_refused_at_set_time(self):
        phone, arm = self._arm()
        self.assertFalse(arm.heat_set_temperature(200).ok)
        self.assertFalse(arm.heat_set_temperature(5).ok)
        self.assertFalse(arm.heat_set_temperature("hot").ok)
        self.assertIsNone(arm.heat.temp_c)      # refused sets leave no state
        self.assertTrue(arm.heat_set_temperature(80).ok)
        self.assertEqual(arm.heat.temp_c, 80)

    def test_cold_heat_does_not_soften(self):
        phone, arm = self._arm()
        arm.heat_set_temperature(40)
        arm.select_tool("heat_plate")
        r = arm.soften_adhesive("back_glass")
        self.assertFalse(r.ok)
        self.assertNotIn("back_glass", phone.adhesive_released)
        self.assertEqual(phone.damage_log, [])

    def test_in_band_heat_softens(self):
        phone, arm = self._arm()
        arm.heat_set_temperature(80)
        arm.select_tool("heat_plate")
        r = arm.soften_adhesive("back_glass")
        self.assertTrue(r.ok)
        self.assertIn("back_glass", phone.adhesive_released)
        self.assertEqual(phone.damage_log, [])

    def test_unset_heat_keeps_legacy_default(self):
        phone, arm = self._arm()
        arm.select_tool("heat_plate")
        r = arm.soften_adhesive("back_glass")
        self.assertTrue(r.ok)
        self.assertIn("back_glass", phone.adhesive_released)

    def test_overheat_certain_damage_above_risk_band(self):
        phone, arm = self._arm()
        arm.heat_set_temperature(140)
        arm.select_tool("heat_plate")
        r = arm.soften_adhesive("back_glass")
        self.assertFalse(r.ok)
        self.assertTrue(r.damage)
        self.assertEqual(len(phone.damage_log), 1)
        # The adhesive DID soften — the heat is the damage, not a failure
        # to soften.
        self.assertIn("back_glass", phone.adhesive_released)

    def test_overheat_roll_band_softens_and_sometimes_burns(self):
        damages = 0
        for seed in range(20):
            phone, arm = self._arm(seed=seed)
            arm.heat_set_temperature(110)
            arm.select_tool("heat_plate")
            arm.soften_adhesive("back_glass")
            self.assertIn("back_glass", phone.adhesive_released)
            damages += len(phone.damage_log)
        self.assertGreater(damages, 0)       # the roll is real
        self.assertLess(damages, 20)       # ...and not a certainty

    def test_overheated_battery_is_a_thermal_event(self):
        phone, arm = self._arm()
        arm.heat_set_temperature(110)   # roll band for glass; certain for battery
        arm.select_tool("heat_plate")
        r = arm.soften_adhesive("battery")
        self.assertFalse(r.ok)
        self.assertTrue(r.damage)
        self.assertEqual(len(phone.damage_log), 1)

    # -- clamp --------------------------------------------------------------
    def _softened_back_glass(self, seed=1):
        phone, arm = self._arm(seed)
        arm.heat_set_temperature(80)
        arm.select_tool("heat_plate")
        arm.soften_adhesive("back_glass")
        arm.select_tool("opening_clamp")
        return phone, arm

    def test_clamp_opens_in_band(self):
        phone, arm = self._softened_back_glass()
        self.assertTrue(arm.op_clamp_engage("back_glass").ok)
        r = arm.op_clamp_open("back_glass", "F2")
        self.assertTrue(r.ok)
        self.assertEqual(phone.damage_log, [])
        self.assertTrue(arm.op_clamp_release().ok)

    def test_clamp_pressure_is_the_default_pull(self):
        phone, arm = self._softened_back_glass()
        self.assertTrue(arm.op_clamp_set_pressure("F3").ok)
        arm.op_clamp_engage("back_glass")
        r = arm.op_clamp_open("back_glass")       # no force: uses the set F3
        self.assertTrue(r.ok)
        self.assertEqual(arm.clamp.open_calls, 1)

    def test_clamp_excessive_force_damages(self):
        phone, arm = self._softened_back_glass()
        arm.op_clamp_engage("back_glass")
        r = arm.op_clamp_open("back_glass", "F4")
        self.assertFalse(r.ok)
        self.assertTrue(r.damage)
        self.assertEqual(len(phone.damage_log), 1)

    def test_clamp_insufficient_pull_makes_no_progress(self):
        phone, arm = self._softened_back_glass()
        arm.op_clamp_engage("back_glass")
        r = arm.op_clamp_open("back_glass", "F1")
        self.assertFalse(r.ok)
        self.assertEqual(phone.damage_log, [])

    def test_clamp_cannot_start_a_cold_seam_at_working_force(self):
        phone, arm = self._arm()
        arm.select_tool("opening_clamp")
        arm.op_clamp_engage("back_glass")
        r = arm.op_clamp_open("back_glass", "F2")
        self.assertFalse(r.ok)
        self.assertNotIn("back_glass", phone.adhesive_released)
        self.assertEqual(phone.damage_log, [])

    def test_clamp_open_requires_engagement(self):
        phone, arm = self._softened_back_glass()
        r = arm.op_clamp_open("back_glass", "F2")
        self.assertFalse(r.ok)

    # -- pry / suction force vs adhesive state ------------------------------
    def test_pry_on_cold_adhesive_makes_no_progress(self):
        phone, arm = self._arm()
        arm.select_tool("spudger")
        r = arm.op_spudger_pry("back_glass", "F2")
        self.assertFalse(r.ok)
        self.assertEqual(phone.damage_log, [])

    def test_pry_firm_on_cold_adhesive_risks_the_crack(self):
        damages = 0
        for seed in range(20):
            phone, arm = self._arm(seed=seed)
            arm.select_tool("spudger")
            r = arm.op_spudger_pry("back_glass", "F3")
            self.assertFalse(r.ok)           # never a clean separation
            damages += len(phone.damage_log)
        self.assertGreater(damages, 0)
        self.assertLess(damages, 20)

    def test_pry_default_unchanged_off_adhesive(self):
        phone, arm = self._arm()
        arm.select_tool("spudger")
        self.assertTrue(arm.op_spudger_pry("display").ok)   # legacy F2 path

    def test_suction_low_force_cannot_start_cold_seam(self):
        phone, arm = self._arm()
        arm.select_tool("suction_cup")
        arm.op_suction_attach("back_glass")
        self.assertFalse(arm.op_suction_pull("back_glass", "F1").ok)
        self.assertTrue(arm.op_suction_pull("back_glass").ok)   # default F2

    def test_unknown_force_levels_refused(self):
        phone, arm = self._arm()
        arm.select_tool("spudger")
        self.assertFalse(arm.op_spudger_pry("display", "F9").ok)
        self.assertFalse(arm.op_clamp_set_pressure("lots").ok)

    # -- visibility -----------------------------------------------------------
    def test_parameters_logged_and_visible(self):
        phone, arm = self._arm()
        arm.heat_set_temperature(80)
        arm.op_clamp_set_pressure("F3")
        obs = arm.observe()
        self.assertEqual(obs["heat_plate"]["temp_c"], 80)
        self.assertEqual(obs["opening_clamp"]["pressure"], "F3")
        actions = [e["action"] for e in arm.log]
        self.assertIn("heat_set_temperature", actions)
        self.assertIn("op_clamp_set_pressure", actions)
        m = arm.metrics()
        self.assertEqual(m["heat_plate"]["temp_c"], 80)
        self.assertGreaterEqual(m["opening_overhead_calls"], 2)


if __name__ == "__main__":
    unittest.main()
