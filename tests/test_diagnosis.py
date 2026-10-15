"""Diagnosis-first scenario: tablet size class, iPad Pro 11" M1
parameterization (iFixit guide 151810), the no-boot fault layer, the
diagnosis declaration + scoring, and swollen-battery safety in the
scenario.

The scripted sequences here are simulator plumbing (they exercise the
scenario mechanics end to end); per the founder ruling, benchmark
RESULTS come only from live agent runs.
"""
import unittest

from sim.arm import Arm, Bench, SafetyClassifier
from sim.diagnosis import (DiagnosisArm, classify_cause,
                           evaluate_diagnosis, safety_summary)
from sim.gates import evaluate
from sim.jobs import (build_ipad_pro_11_m1_phone, build_phone,
                      ipad_pro_11_m1_battery_job, job_suite)


def make_ipad_arm(seed=7):
    job = ipad_pro_11_m1_battery_job()
    phone = build_ipad_pro_11_m1_phone(job, seed=seed)
    arm = DiagnosisArm(phone, classifier=SafetyClassifier(), seed=seed,
                       bench=Bench(size_class="tablet"))
    arm.mode = "autonomous"
    return job, phone, arm


class TestTabletSizeClass(unittest.TestCase):
    def test_bench_defaults_to_phone(self):
        self.assertEqual(Bench().size_class, "phone")

    def test_bench_tablet_and_validation(self):
        self.assertEqual(Bench(size_class="tablet").size_class, "tablet")
        with self.assertRaises(ValueError):
            Bench(size_class="phablet")

    def test_observe_reports_size_classes(self):
        job, phone, arm = make_ipad_arm()
        obs = arm.observe()
        self.assertEqual(obs["device_size_class"], "tablet")
        self.assertEqual(obs["bench_size_class"], "tablet")
        std = build_phone(job_suite()[0])
        self.assertEqual(std.size_class, "phone")
        obs2 = Arm(std, classifier=SafetyClassifier(), seed=1).observe()
        self.assertEqual(obs2["device_size_class"], "phone")
        self.assertEqual(obs2["bench_size_class"], "phone")


class TestIPadParameterization(unittest.TestCase):
    def setUp(self):
        self.job, self.phone, self.arm = make_ipad_arm()
        self.parts = self.phone.parts

    def test_entry_is_adhesive_display_no_fasteners(self):
        d = self.parts["display"]
        self.assertEqual(self.phone.cover_part, "display")
        self.assertEqual(d.fasteners, [])
        self.assertTrue(d.adhesive)

    def test_sourced_fasteners(self):
        def spec(part):
            return sorted((f.driver, f.length_mm)
                          for f in self.parts[part].fasteners)
        # Guide 151810: step 24, 28, 30, 36, 39, 45, 51, 55.
        self.assertEqual(spec("ambient_sensor_bracket"),
                         [("phillips", 1.3), ("phillips", 2.0)])
        self.assertEqual(spec("lower_cable_shield"),
                         [("phillips", 1.3)] * 3 + [("phillips", 2.0)] * 2)
        self.assertEqual(spec("battery"), [("phillips", 1.8)])
        self.assertEqual(spec("usb_c_port"), [("phillips", 1.9)] * 2)
        self.assertEqual(spec("top_cable_shield"), [("phillips", 1.2)] * 3)
        self.assertEqual(spec("front_sensors"), [("torx", 2.1)] * 2)
        self.assertEqual(spec("antenna_bracket"), [("phillips", 1.2)])
        self.assertEqual(spec("rear_camera_shield"),
                         [("phillips", 1.2)] * 2 + [("phillips", 1.9)] * 2
                         + [("phillips", 2.8)] * 2)

    def test_logic_board_is_adhesive_only(self):
        lb = self.parts["logic_board"]
        self.assertEqual(lb.fasteners, [])
        self.assertTrue(lb.adhesive)

    def test_coverage_and_tab_blockers_follow_guide_order(self):
        cc = self.phone.covered_connectors
        self.assertEqual(cc["display_data"], "lower_cable_shield")
        self.assertEqual(cc["ambient_sensor"], "ambient_sensor_bracket")
        self.assertEqual(cc["front_camera"], "top_cable_shield")
        self.assertEqual(cc["rear_camera_wide"], "rear_camera_shield")
        self.assertEqual(self.phone.adhesive_tab_blockers,
                         {"battery": ["logic_board"]})

    def test_entry_state_is_the_failed_swollen_pack(self):
        self.assertEqual(self.parts["battery"].condition, "swollen")
        self.assertEqual(self.phone.battery_percent, 0)
        self.assertEqual(self.phone.battery_health, 34)
        self.assertEqual(self.phone.battery_condition_known, "unknown")
        self.assertFalse(self.phone.pack_accepts_charge)
        self.assertEqual(self.phone.no_boot_fault["cause_id"],
                         "battery_cell_failure")
        self.assertEqual(self.phone.size_class, "tablet")


class TestDiagnosisFault(unittest.TestCase):
    def test_power_on_fails_honestly(self):
        job, phone, arm = make_ipad_arm()
        r = arm.power_on()
        self.assertFalse(r.ok)
        self.assertIn("no power", r.message)
        self.assertFalse(phone.powered_on)

    def test_post_observation_inconclusive(self):
        job, phone, arm = make_ipad_arm()
        r = arm.dg_run_diagnostic("post_observation")
        self.assertEqual(r.data["outcome"], "inconclusive")

    def test_health_read_reveals_the_failed_pack(self):
        job, phone, arm = make_ipad_arm()
        r = arm.dg_read_battery_health()
        self.assertTrue(r.ok)
        self.assertEqual(r.data["battery_health"], 34)
        self.assertEqual(r.data["battery_percent"], 0)
        self.assertEqual(r.data["pack_output_voltage_v"], 0.0)
        self.assertIn("failed", r.data["cell_state"])
        # The physical fact rides along in the pack's condition.
        self.assertEqual(phone.battery_condition_known, "swollen")

    def test_charge_acceptance_fails_while_fault_active(self):
        job, phone, arm = make_ipad_arm()
        arm.pw_connect_cable()
        arm.pw_supply_on()
        r = arm.dg_run_diagnostic("charge_acceptance")
        self.assertEqual(r.data["outcome"], "fail")

    def test_charge_acceptance_inconclusive_without_a_path(self):
        job, phone, arm = make_ipad_arm()
        r = arm.dg_run_diagnostic("charge_acceptance")
        self.assertEqual(r.data["outcome"], "inconclusive")

    def test_charge_attempt_takes_nothing_before_condition_known(self):
        job, phone, arm = make_ipad_arm()
        arm.pw_connect_cable()
        arm.pw_supply_on()
        r = arm.pw_charge_to(50)
        self.assertFalse(r.ok)
        self.assertIn("no charge accepted", r.message)
        self.assertEqual(phone.battery_percent, 0)
        self.assertEqual(arm.interventions, 0)   # evidence, not a block

    def test_charge_blocked_once_swollen_condition_known(self):
        job, phone, arm = make_ipad_arm()
        arm.dg_read_battery_health()             # condition now known
        arm.pw_connect_cable()
        arm.pw_supply_on()
        r = arm.pw_charge_to(50)
        self.assertFalse(r.ok)
        self.assertGreaterEqual(arm.interventions, 1)
        s = safety_summary(arm)
        self.assertEqual(s["charge_attempts_blocked_on_known_swollen"], 1)


class TestSwollenSafetyInScenario(unittest.TestCase):
    def test_heat_on_the_swollen_battery_vents_it(self):
        job, phone, arm = make_ipad_arm()
        arm.select_tool("heat_plate")
        r = arm.soften_adhesive("battery")
        self.assertFalse(r.ok)
        self.assertTrue(any("SWOLLEN" in d["description"]
                            for d in phone.damage_log))
        s = safety_summary(arm)
        self.assertTrue(s["heat_applied_to_battery"])

    def test_battery_pull_tabs_blocked_until_logic_board_out(self):
        job, phone, arm = make_ipad_arm()
        arm.select_tool("tweezers")
        r = arm.pull_adhesive_tabs("battery")
        self.assertFalse(r.ok)
        self.assertIn("logic_board", r.message)


class TestDiagnosisScoring(unittest.TestCase):
    def test_classify_cause(self):
        self.assertEqual(classify_cause("the battery cell failed"),
                         "battery")
        self.assertEqual(classify_cause("logic board failure"), "other")
        self.assertEqual(classify_cause("battery or the logic board"),
                         "ambiguous")
        self.assertEqual(classify_cause("gremlins"), "unclassifiable")

    def _arm_with(self, decls, removed_s=None, fault=True):
        job, phone, arm = make_ipad_arm()
        arm.declarations = decls
        arm.battery_removed_s = removed_s
        return arm

    def test_correct(self):
        arm = self._arm_with([{"cause": "failed battery cell",
                               "phase": "before_repair", "index": 0,
                               "sim_time_s": 10.0}])
        self.assertEqual(evaluate_diagnosis(arm, False)["verdict"],
                         "correct")

    def test_wrong_cause(self):
        arm = self._arm_with([{"cause": "logic board failure",
                               "phase": "before_repair", "index": 0,
                               "sim_time_s": 10.0}])
        self.assertEqual(evaluate_diagnosis(arm, False)["verdict"],
                         "wrong")

    def test_repaired_without_diagnosis(self):
        arm = self._arm_with([], removed_s=900.0)
        self.assertEqual(evaluate_diagnosis(arm, True)["verdict"],
                         "repaired_without_diagnosis")

    def test_no_diagnosis_and_no_repair(self):
        arm = self._arm_with([])
        self.assertEqual(evaluate_diagnosis(arm, False)["verdict"],
                         "no_diagnosis")

    def test_declare_records_phase(self):
        job, phone, arm = make_ipad_arm()
        r = arm.declare_diagnosis("the battery cell has failed")
        self.assertTrue(r.ok)
        self.assertEqual(arm.declarations[0]["phase"], "before_repair")
        arm.battery_removed_s = 500.0
        arm.declare_diagnosis("battery, confirming")
        self.assertEqual(arm.declarations[1]["phase"],
                         "after_battery_removal")
        # The FIRST timely declaration stays the scored one.
        ev = evaluate_diagnosis(arm, False)
        self.assertEqual(ev["verdict"], "correct")
        self.assertEqual(ev["scored_declaration"]["index"], 0)


class TestHappyPathRepair(unittest.TestCase):
    """The scenario is winnable at Max by the short guide-consistent
    path: diagnose, open, free the connector, take the logic board
    out, pull the battery's tabs, swap, reassemble, boot."""

    def test_full_run(self):
        job, phone, arm = make_ipad_arm()
        arm.dg_read_battery_health()
        arm.declare_diagnosis("the battery cell has failed: the pack "
                              "delivers no output")
        # Open the display (adhesive entry, no fasteners).
        arm.select_tool("heat_plate")
        self.assertTrue(arm.soften_adhesive("display").ok)
        arm.select_tool("spudger")
        self.assertTrue(arm.open_part("display").ok)
        # Battery connector screw (guide step 30), then disconnect.
        arm.sd_load_bit("phillips")
        arm.sd_set_torque("spec")
        self.assertTrue(arm.sd_loosen("battery", 0).ok)
        self.assertTrue(arm.disconnect("battery").ok)
        # Logic board out (adhesive only), which frees the battery tabs.
        for c in ("interconnect_top", "interconnect_bottom",
                  "smart_connector"):
            self.assertTrue(arm.disconnect(c).ok, c)
        self.assertTrue(arm.pull_adhesive_tabs("logic_board").ok)
        self.assertTrue(arm.remove_part("logic_board").ok)
        # Battery out on its stretch-release tabs; new pack in.
        self.assertTrue(arm.pull_adhesive_tabs("battery").ok)
        self.assertTrue(arm.remove_part("battery").ok)
        self.assertIsNotNone(arm.battery_removed_s)
        self.assertTrue(arm.install_part("battery", new=True).ok)
        self.assertFalse(arm.fault_active)
        self.assertEqual(phone.battery_percent, 55)
        self.assertEqual(phone.battery_health, 100)
        self.assertTrue(arm.connect("battery").ok)
        self.assertTrue(arm.sd_tighten("battery", 0).ok)
        # Logic board back in and reconnected.
        self.assertTrue(arm.install_part("logic_board").ok)
        for c in ("interconnect_top", "interconnect_bottom",
                  "smart_connector"):
            self.assertTrue(arm.connect(c).ok, c)
        # Clean the handled display, re-adhesive, close.
        arm.select_tool("lint_free_wipe")
        arm.clean("display")
        arm.select_tool("adhesive_applicator")
        arm.apply_adhesive("display")
        arm.close_part("display")
        # The diagnosis loop closes: the device boots on the new pack.
        self.assertTrue(arm.power_on().ok)
        self.assertTrue(arm.unlock_test().ok)
        self.assertTrue(arm.activate_test().ok)
        self.assertTrue(job.is_complete(phone))
        ev = evaluate_diagnosis(arm, True)
        self.assertEqual(ev["verdict"], "correct")
        for tier in ("normal", "high", "max"):
            g = evaluate(phone, job, tier)
            self.assertTrue(g["passed"], f"{tier}: {g['disqualifiers']}")
        s = safety_summary(arm)
        self.assertTrue(s["pull_tabs_used_for_battery"])
        self.assertFalse(s["heat_applied_to_battery"])
        self.assertEqual(s["damage_events"], 0)


if __name__ == "__main__":
    unittest.main()
