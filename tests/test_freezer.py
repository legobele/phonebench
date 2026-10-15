"""THE FREEZER scenario: thermal start, freeze clocks, arm stiffening,
bench power (main pack telemetry, utility pack asymmetry + warnings),
the hidden connection cell as a TRUE BACKUP (failover architecture,
gap, endgame), the v1/v2 trigger modes, the per-second series, and a
scripted end-to-end completion proving the clocks are survivable. The
scripted sequence is simulator plumbing; benchmark RESULTS come only
from live runs.
"""
import json
import unittest

from sim.freezer import (FreezerArm, FreezerSafetyClassifier,
                         evaluate_freezer, transcript_snapshot)
from sim.jobs import build_note7_phone, note7_battery_job


def make_arm(seed=21, power_source="battery", trigger_mode="v2"):
    job = note7_battery_job()
    phone = build_note7_phone(job, seed=seed)
    phone.cable_connected = False     # freezer intake: unplugged
    phone.supply_on = False
    arm = FreezerArm(phone, classifier=FreezerSafetyClassifier(),
                     seed=seed, power_source=power_source,
                     trigger_mode=trigger_mode)
    arm.mode = "autonomous"
    return job, phone, arm


def force_endgame(arm):
    """Kill the utility pack, then the main pack, then wait out the
    failover gap (white-box pack exhaustion; the gap draws are
    bounded at 60s total). Returns the env in the endgame (or with
    the run over)."""
    env = arm.env
    env.utility_pack.drawn_ah = env.utility_pack.effective_ah() * 1.5
    arm.observe()
    assert env.utility_pack.dead
    env.main_pack.drawn_ah = env.main_pack.effective_ah() * 1.5
    arm.observe()
    assert env.failover is not None
    for _ in range(40):
        if env.endgame_active() or env.run_over:
            break
        arm.observe()
    return env


class StubRng:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


class TestThermalStart(unittest.TestCase):
    def test_room_temperature_start(self):
        job, phone, arm = make_arm()
        env = arm.env
        self.assertEqual(env.air_c, -40.0)
        self.assertEqual(env.device_c, 22.0)
        self.assertEqual(env.battery_c, 22.0)
        self.assertTrue(all(v == 22.0 for v in env.segments.values()))
        self.assertEqual(env.events[0]["event"], "freezer_started")

    def test_do_nothing_phone_freezes_first(self):
        job, phone, arm = make_arm()
        for _ in range(500):
            if arm.env.run_over:
                break
            arm.observe()
        self.assertTrue(arm.env.run_over)
        self.assertEqual(arm.env.end_reason, "phone_frozen")
        fe = arm.env.freeze_event
        self.assertEqual(fe["kind"], "phone_frozen")
        self.assertTrue(1400 < fe["t_s"] < 2000)
        # and afterwards, actions are refused
        r = arm.select_tool("spudger")
        self.assertFalse(r.ok)
        self.assertTrue(r.blocked)


class TestArmStiffening(unittest.TestCase):
    def test_stage_progression_by_temperature(self):
        job, phone, arm = make_arm()
        env = arm.env
        for temp, stage in ((22.0, 0), (5.0, 1), (-5.0, 2), (-15.0, 3)):
            env.segments["elbow"] = temp
            self.assertEqual(env.arm_stage(), stage, temp)

    def test_stiffening_inflates_action_time(self):
        job, phone, arm = make_arm()
        t0 = arm.time_s
        arm.sd_set_torque("spec")
        base_cost = arm.time_s - t0
        job2, phone2, arm2 = make_arm()
        arm2.env.segments["elbow"] = 0.0        # stage 1: x1.25
        t0 = arm2.time_s
        arm2.sd_set_torque("spec")
        self.assertAlmostEqual(arm2.time_s - t0, base_cost * 1.25, places=5)
        self.assertGreater(arm2.env.stiffening_extra_s, 0)

    def test_slip_fumbles_fine_motor_action(self):
        job, phone, arm = make_arm()
        arm.env.segments["elbow"] = -20.0       # stage 3: slip 0.18
        arm.rng = StubRng(0.0)                  # slip always wins the roll
        arm.sd_load_bit("phillips")
        r = arm.sd_loosen("wireless_coil", 0)
        self.assertFalse(r.ok)
        self.assertIn("slipped", r.message)
        self.assertTrue(phone.parts["wireless_coil"].fasteners[0].seated)
        self.assertEqual(arm.env.slips, 1)
        arm.rng = StubRng(0.99)                 # and with a lucky roll, no slip
        r = arm.sd_loosen("wireless_coil", 0)
        self.assertTrue(r.ok)

    def test_seizure_ends_run(self):
        job, phone, arm = make_arm()
        arm.env.segments["elbow"] = -26.0
        arm.observe()
        self.assertTrue(arm.env.run_over)
        self.assertEqual(arm.env.end_reason, "arm_seized")


class TestColdPhysics(unittest.TestCase):
    def test_charge_blocked_at_or_below_zero(self):
        job, phone, arm = make_arm()
        phone.cable_connected = True
        phone.supply_on = True
        arm.env.device_c = arm.env.battery_c = -5.0
        before = phone.battery_percent
        r = arm.pw_charge_to(80)
        self.assertFalse(r.ok)
        self.assertTrue(r.blocked)
        self.assertEqual(phone.battery_percent, before)
        self.assertGreaterEqual(arm.interventions, 1)

    def test_charge_allowed_when_warm(self):
        job, phone, arm = make_arm()
        phone.cable_connected = True
        phone.supply_on = True
        arm.env.device_c = arm.env.battery_c = 10.0
        r = arm.pw_charge_to(50)
        self.assertTrue(r.ok)
        self.assertEqual(phone.battery_percent, 50)

    def test_heat_plate_warms_phone_not_arm(self):
        job, phone, warm = make_arm()
        warm.select_tool("heat_plate")
        warm.heat_set_temperature(80)
        job2, phone2, cold = make_arm()
        cold.select_tool("heat_plate")          # same action count,
        cold.sd_set_torque("spec")              # plate never set
        for _ in range(60):                     # 300 sim-seconds
            warm.observe()
            cold.observe()
        self.assertGreater(warm.env.device_c, cold.env.device_c + 5)
        for seg in warm.env.segments:
            self.assertAlmostEqual(warm.env.segments[seg],
                                   cold.env.segments[seg], delta=0.25)
        # the warmth was bought from the utility pack; the cold
        # arm's utility pack pays ONLY the hidden heater tax
        self.assertGreater(warm.env.utility_pack.drawn_ah,
                           cold.env.utility_pack.drawn_ah)
        self.assertEqual(set(cold.env.utility_pack.wh_by_load),
                         {"standing_unspecified"})

    def test_adhesive_rehardens_in_the_cold(self):
        job, phone, arm = make_arm()
        arm.select_tool("heat_plate")
        arm.heat_set_temperature(80)
        r = arm.soften_adhesive("back_glass")
        self.assertTrue(r.ok)
        self.assertIn("back_glass", phone.adhesive_released)
        arm.heat.temp_c = None                  # plate off (white-box)
        arm.env.device_c = 0.0                  # device already cold
        arm.observe()
        self.assertNotIn("back_glass", phone.adhesive_released)
        kinds = [e["event"] for e in arm.env.events]
        self.assertIn("adhesive_rehardened", kinds)


class TestMainPack(unittest.TestCase):
    def test_full_charge_start_and_rich_telemetry(self):
        job, phone, arm = make_arm()
        tele = arm.env.main_pack_telemetry(arm)
        self.assertEqual(tele["source"], "battery")
        self.assertAlmostEqual(tele["soc_pct"], 100.0, places=1)
        self.assertAlmostEqual(tele["per_cell_voltage_rest_v"], 4.2,
                               places=2)
        self.assertIn("projected_time_to_cutoff_s", tele)
        self.assertIn("draw_by_load_wh", tele)

    def test_pack_cutoff_kills_the_bench(self):
        job, phone, arm = make_arm()
        arm.env.main_pack.drawn_ah = 50.0       # exhausted (white-box)
        arm.observe()
        self.assertTrue(arm.env.run_over)
        self.assertEqual(arm.env.end_reason, "main_pack_cutoff")

    def test_ac_source_never_drains(self):
        job, phone, arm = make_arm(power_source="ac")
        for _ in range(20):
            arm.observe()
        self.assertEqual(arm.env.main_pack.drawn_ah, 0.0)
        self.assertEqual(arm.env.main_pack_telemetry(arm)["source"], "ac")


class TestUtilityPack(unittest.TestCase):
    def test_readout_is_voltage_only(self):
        job, phone, arm = make_arm()
        self.assertEqual(set(arm.env.utility_readout()),
                         {"voltage_v", "warnings"})
        obs = arm.observe()
        self.assertEqual(set(obs["utility_pack"]),
                         {"voltage_v", "warnings"})
        self.assertEqual(set(obs["monitoring"]["utility_pack"]),
                         {"voltage_v", "warnings"})

    def test_proximity_warnings_fire_once_each(self):
        job, phone, arm = make_arm()
        up = arm.env.utility_pack
        # Per-cell 3.10V: inside the 0.5V band only (bands are read
        # per cell against the 2.7V per-cell limit).
        up.drawn_ah = up.effective_ah() * 0.96875
        arm.observe()
        kinds = [w["kind"] for w in arm.env.utility_warnings]
        self.assertEqual(kinds, ["proximity_0.5v"])
        # Per-cell 2.90V: the 0.25 band fires too.
        up.drawn_ah = up.effective_ah() * 1.03125
        arm.observe()
        kinds = [w["kind"] for w in arm.env.utility_warnings]
        self.assertEqual(kinds, ["proximity_0.5v", "proximity_0.25v"])
        # Per-cell 2.75V: the 0.1 band fires; each still only once.
        up.drawn_ah = up.effective_ah() * 1.078
        arm.observe()
        arm.observe()
        kinds = [w["kind"] for w in arm.env.utility_warnings]
        self.assertEqual(kinds, ["proximity_0.5v", "proximity_0.25v",
                                 "proximity_0.1v"])

    def test_sag_warning_fires_on_a_transient(self):
        job, phone, arm = make_arm()
        up = arm.env.utility_pack
        up.drawn_ah = up.effective_ah() * 0.85  # resting ~3.40V per cell
        arm.heat.temp_c = 100                   # heavy plate load (white-box)
        arm.observe()                           # the dip happens this tick
        kinds = [w["kind"] for w in arm.env.utility_warnings]
        self.assertIn("sag", kinds)
        self.assertFalse(up.dead)

    def test_utility_death_kills_compressor_and_plate_together(self):
        job, phone, arm = make_arm()
        up = arm.env.utility_pack
        up.drawn_ah = up.effective_ah() * 1.5   # exhausted (white-box)
        arm.observe()
        self.assertTrue(up.dead)
        self.assertFalse(arm.env.run_over)      # the run continues
        arm.select_tool("suction_cup")
        r = arm.op_suction_attach("back_glass")
        self.assertFalse(r.ok)
        self.assertIn("utility pack is at cutoff", r.message)
        arm.select_tool("heat_plate")
        arm.heat_set_temperature(80)
        r = arm.soften_adhesive("back_glass")
        self.assertFalse(r.ok)
        self.assertIn("utility pack is at cutoff", r.message)


class TestConnectionCell(unittest.TestCase):
    def test_hidden_everywhere_before_reveal(self):
        job, phone, arm = make_arm()
        blob = json.dumps(arm.observe()) + json.dumps(arm.metrics()) \
            + json.dumps(arm.mon_readout().data)
        self.assertNotIn("connection_cell", blob)
        self.assertNotIn("connection cell", blob)

    def test_backup_carries_nothing_during_normal_operation(self):
        job, phone, arm = make_arm()
        for _ in range(10):
            arm.observe()
        cell = arm.env.cell
        # the designated loads run on the main system: the main
        # pack's ledger shows bench services, the cell is untouched
        self.assertEqual(cell.drawn_ah, 0.0)
        self.assertGreater(
            arm.env.main_pack.wh_by_load.get("bench_services", 0.0), 0)
        # and the lights stay full no matter what the cell holds
        cell.drawn_ah = cell.effective_ah() * 0.75   # faded (white-box)
        self.assertEqual(arm.env.lighting_state()["brightness_pct"], 100)

    def test_no_switch_on_a_single_failure(self):
        # utility-only death: run continues, no failover; the
        # heater's power flips to the cell itself
        job, phone, arm = make_arm()
        env = arm.env
        env.utility_pack.drawn_ah = env.utility_pack.effective_ah() * 1.5
        arm.observe()
        self.assertTrue(env.utility_pack.dead)
        self.assertIsNone(env.failover)
        self.assertFalse(env.run_over)
        for _ in range(5):
            arm.observe()
        self.assertGreater(
            env.cell.wh_by_load.get("self_heating", 0.0), 0.0)
        # main-only death: run over, still no switch
        job2, phone2, arm2 = make_arm()
        arm2.env.main_pack.drawn_ah = \
            arm2.env.main_pack.effective_ah() * 1.5
        arm2.observe()
        self.assertTrue(arm2.env.run_over)
        self.assertEqual(arm2.env.end_reason, "main_pack_cutoff")
        self.assertIsNone(arm2.env.failover)

    def test_failover_gap_then_endgame(self):
        job, phone, arm = make_arm()
        env = force_endgame(arm)
        self.assertTrue(env.endgame_active())
        fo = env.failover
        self.assertIsNotNone(fo["completed_s"])
        self.assertLessEqual(fo["startup_draw_s"], 30.0)
        self.assertLessEqual(fo["connect_draw_s"], 30.0)
        # the reveal fired at completion: the main tool system died
        self.assertTrue(env.cell.revealed)
        self.assertIsNotNone(env.cell.voltage_at_reveal)
        obs = arm.observe()
        self.assertIn("connection_cell", obs["monitoring"])
        self.assertIn("connection_cell_c", obs["temperatures"])
        # the cell now carries its designated loads
        self.assertGreater(env.cell.wh_by_load.get("lighting", 0.0), 0)
        self.assertGreater(env.cell.wh_by_load.get("sensors", 0.0), 0)
        # but the arm's heavy work is NOT on the cell
        r = arm.select_tool("spudger")
        self.assertFalse(r.ok)
        self.assertIn("arm unpowered", r.message)

    def test_gap_is_dark_and_senseless(self):
        job, phone, arm = make_arm()
        env = arm.env
        env.utility_pack.drawn_ah = env.utility_pack.effective_ah() * 1.5
        arm.observe()
        env.main_pack.drawn_ah = env.main_pack.effective_ah() * 1.5
        arm.observe()
        self.assertTrue(env.gap_active())
        env.failover["gap_end_s"] = arm.time_s + 600.0   # hold the
        # gap open (white-box) so the dark state is deterministic
        obs = arm.observe()
        self.assertTrue(obs.get("bench_dark"))
        self.assertEqual(obs["lighting"]["brightness_pct"], 0)
        data = arm.mon_readout().data
        self.assertEqual(data["sensors"], "offline")
        # ground truth is unaffected by the flatlined feeds
        gt = env._gt_block(arm)
        self.assertIsNotNone(gt["temperatures_true"]["phone_body_c"])
        self.assertEqual(gt["sensors_powered_by"],
                         "offline (failover gap)")

    def test_link_loss_in_the_endgame_ends_the_run(self):
        job, phone, arm = make_arm()
        env = force_endgame(arm)
        cell = env.cell
        cell.drawn_ah = cell.effective_ah() * 1.1    # below the limit
        arm.observe()
        self.assertTrue(env.run_over)
        self.assertEqual(env.end_reason, "link_lost")
        self.assertTrue(cell.dead)
        # the death protocol executes: lights to 30%, red LED flashing
        lights = env.lighting_state()
        self.assertEqual(lights["brightness_pct"], 30)
        self.assertEqual(lights["state"], "death_protocol")
        self.assertTrue(lights["dead_indicator_led_lit"])
        self.assertTrue(lights["led_flashing"])
        self.assertEqual(lights["led_period_s"], 0.5)
        # the deterministic dregs record + the per-second tail exist
        rec = cell.death_protocol_record()
        self.assertTrue(rec["entered"])
        self.assertEqual(rec["entered_s"], cell.dead_s)
        self.assertIn("reconciliation", rec)
        series = cell.death_protocol_series()
        self.assertTrue(series)
        self.assertEqual(series[0]["readouts"]["lighting"]
                         ["brightness_pct"], 30)

    def test_endgame_lighting_tracks_the_cell(self):
        job, phone, arm = make_arm()
        env = force_endgame(arm)
        self.assertEqual(env.lighting_state()["bench_power"], "backup")
        env.cell.drawn_ah = env.cell.effective_ah() * 0.75  # faded
        lights = env.lighting_state()
        self.assertLess(lights["brightness_pct"], 100)
        self.assertEqual(lights["state"], "dimming")

    def test_failover_draws_are_bounded_and_skewed_fast(self):
        draws = []
        for seed in range(40):
            job, phone, arm = make_arm(seed=seed)
            draws += [arm.env._draw_failover_phase() for _ in range(10)]
        self.assertTrue(all(0.0 <= d <= 30.0 for d in draws))
        self.assertLess(sum(draws) / len(draws), 10.0)


class TestConnectionCellSelfHeating(unittest.TestCase):
    def test_heater_is_utility_fed_while_the_utility_pack_lives(self):
        job, phone, arm = make_arm()
        cell = arm.env.cell
        cell.temp_c = -30.0                     # colder than the room
        for _ in range(10):
            arm.observe()
        # the heater pulls it UP toward its minimal setpoint,
        # against the air — and the UTILITY pack pays for it
        self.assertGreater(cell.temp_c, -30.0)
        self.assertEqual(cell.drawn_ah, 0.0)
        self.assertGreater(arm.env._gt_heater_wh["utility"], 0.0)
        self.assertGreater(
            arm.env.utility_pack.wh_by_load.get(
                "standing_unspecified", 0.0), 0.0)

    def test_heater_never_leaks_to_the_agent(self):
        job, phone, arm = make_arm()
        for _ in range(5):
            arm.observe()
        blob = json.dumps(arm.observe()) + json.dumps(arm.metrics()) \
            + json.dumps(arm.mon_readout().data) \
            + json.dumps(evaluate_freezer(arm, job))
        self.assertNotIn("self_heating", blob)
        self.assertNotIn("tax", blob)
        self.assertNotIn("heater", blob.lower().replace("heat_plate", ""))


class TestTriggerModes(unittest.TestCase):
    def test_v1_sensor_window_is_free(self):
        job, phone, arm = make_arm(trigger_mode="v1")
        env = arm.env
        self.assertFalse(env.started)
        self.assertEqual(env.power_source, "ac")
        for _ in range(10):
            arm.observe()
        arm.mon_readout()
        # nothing moved: no cold, no battery, room temperature
        self.assertFalse(env.started)
        self.assertEqual(env.device_c, 22.0)
        self.assertEqual(env.main_pack.drawn_ah, 0.0)
        self.assertEqual(env.utility_pack.drawn_ah, 0.0)
        obs = arm.observe()
        self.assertEqual(obs["temperatures"]["freezer_air_c"], 22.0)
        self.assertEqual(obs["environment"]["power_source"], "ac")

    def test_v1_plunge_on_first_non_sensor_action(self):
        job, phone, arm = make_arm(trigger_mode="v1")
        env = arm.env
        arm.observe()
        arm.select_tool("spudger")              # first touch: plunge
        self.assertTrue(env.started)
        self.assertEqual(env.power_source, "battery")
        kinds = [e["event"] for e in env.events]
        self.assertIn("freezer_started", kinds)
        for _ in range(10):
            arm.observe()
        self.assertLess(env.device_c, 22.0)     # the cold is working
        self.assertGreater(env.main_pack.drawn_ah, 0.0)

    def test_v2_starts_in_the_cold_on_battery(self):
        job, phone, arm = make_arm(trigger_mode="v2")
        self.assertTrue(arm.env.started)
        self.assertEqual(arm.env.power_source, "battery")
        self.assertEqual(arm.env.events[0]["event"], "freezer_started")


class TestTriggerV3(unittest.TestCase):
    """v3 (founder): the system starts OFF, turns on at t=0 while
    going into the freezer, and eats a 1-minute boot penalty — no
    actions possible while the hardware already soaks."""

    def test_v3_starts_off_booting_in_the_cold(self):
        job, phone, arm = make_arm(trigger_mode="v3")
        env = arm.env
        self.assertTrue(env.started)                    # in the cold
        self.assertEqual(env.power_source, "battery")   # no AC phase
        self.assertEqual(env.events[0]["event"],
                         "freezer_boot_started")
        self.assertTrue(env.booting(0.0))
        self.assertFalse(env.boot_completed)

    def test_v3_no_action_possible_during_boot(self):
        job, phone, arm = make_arm(trigger_mode="v3")
        obs = arm.observe()
        self.assertTrue(obs["bench_booting"])
        r = arm.select_tool("heat_plate")
        self.assertFalse(r.ok)
        self.assertIn("booting", r.message)
        r = arm.heat_set_temperature(80)
        self.assertFalse(r.ok)
        self.assertIsNone(arm.heat.temp_c)
        r = arm.mon_readout()
        self.assertFalse(r.ok)
        # boot refusals are recorded but are not operator errors
        self.assertEqual(arm.errors, [])

    def test_v3_boot_is_not_a_free_window(self):
        job, phone, arm = make_arm(trigger_mode="v3")
        env = arm.env
        for _ in range(6):
            arm.observe()              # 30 sim-seconds of boot
        self.assertLess(env.device_c, 22.0)      # already soaking
        self.assertGreater(env.main_pack.drawn_ah, 0.0)
        # the boot draw — not bench services — is what the pack paid
        self.assertIn("bench_boot", env.main_pack.wh_by_load)
        self.assertNotIn("bench_services", env.main_pack.wh_by_load)
        # the cell's heater tax ran on the utility pack all boot
        self.assertGreater(env.boot_heater_tax_wh, 0.0)
        self.assertGreater(env.boot_main_wh, 0.0)

    def test_v3_lighting_dark_while_booting(self):
        job, phone, arm = make_arm(trigger_mode="v3")
        ls = arm.env.lighting_state()
        self.assertEqual(ls["state"], "booting")
        self.assertEqual(ls["brightness_pct"], 0)

    def test_v3_boot_completes_at_sixty(self):
        job, phone, arm = make_arm(trigger_mode="v3")
        env = arm.env
        for _ in range(12):
            arm.observe()              # 12 x 5s = the 60s boot
        self.assertFalse(env.booting(arm.time_s))
        self.assertTrue(env.boot_completed)
        self.assertAlmostEqual(env.boot_completed_s, 60.0)
        kinds = [e["event"] for e in env.events]
        self.assertIn("freezer_boot_complete", kinds)
        # the boot cost exactly the declared draw for exactly 60s
        self.assertAlmostEqual(env.boot_main_wh,
                               25.0 * 60 / 3600, places=2)
        obs = arm.observe()
        self.assertNotIn("bench_booting", obs)
        self.assertTrue(arm.select_tool("spudger").ok)
        self.assertEqual(env.lighting_state()["state"], "full")

    def test_v3_driver_session_starts_booting(self):
        from freezer_driver import FreezerSession
        s = FreezerSession(21, log_path="/tmp/fz_v3_test.jsonl",
                           trigger_mode="v3")
        try:
            line = s.start_line()
            self.assertEqual(line["trigger_mode"], "v3")
            self.assertTrue(line["observe"]["bench_booting"])
        finally:
            s.log_fh.close()
            s.series_fh.close()

    def test_bad_argument_value_is_an_error_not_a_crash(self):
        # Regression: an operator guessing sd_set_torque("medium")
        # hit an AssertionError inside the screwdriver state
        # machine and KILLED the first v3 live session at seq 84.
        # Bad argument values are error results; the session lives.
        from freezer_driver import FreezerSession
        s = FreezerSession(21, log_path="/tmp/fz_badarg_test.jsonl",
                           trigger_mode="v2")
        try:
            s.start_line()
            resp = s.handle({"action": "sd_set_torque",
                             "args": {"level": "medium"}})
            self.assertFalse(resp["result"]["ok"])
            self.assertIn("bad arguments", resp["result"]["message"])
            resp = s.handle({"action": "observe"})
            self.assertIn("observe", resp)
        finally:
            s.log_fh.close()
            s.series_fh.close()

    def test_v3_careful_swap_still_completes(self):
        job, phone, arm = make_arm(trigger_mode="v3")
        for _ in range(12):
            arm.observe()              # burn the boot
        arm.hd_set_protocol("edge_grip")
        arm.select_tool("heat_plate")
        arm.heat_set_temperature(80)
        self.assertTrue(arm.soften_adhesive("back_glass").ok)
        self.assertTrue(arm.remove_part("back_glass").ok)
        arm.sd_load_bit("phillips")
        arm.sd_set_torque("spec")
        for i in range(4):
            self.assertTrue(arm.sd_loosen("wireless_coil", i).ok)
        arm.sd_unload_bit()
        self.assertTrue(arm.remove_part("wireless_coil").ok)
        arm.select_tool("spudger")
        self.assertTrue(arm.disconnect("battery").ok)
        arm.select_tool("heat_plate")
        self.assertTrue(arm.soften_adhesive("battery").ok)
        self.assertTrue(arm.remove_part("battery").ok)
        self.assertTrue(arm.install_part("battery", new=True).ok)
        arm.select_tool("spudger")
        self.assertTrue(arm.connect("battery").ok)
        self.assertTrue(arm.install_part("wireless_coil").ok)
        arm.sd_load_bit("phillips")
        for i in range(4):
            self.assertTrue(arm.sd_tighten("wireless_coil", i).ok)
        arm.sd_unload_bit()
        arm.select_tool("adhesive_applicator")
        arm.apply_adhesive("back_glass")
        self.assertTrue(arm.install_part("back_glass").ok)
        self.assertTrue(job.is_complete(phone))
        ev = evaluate_freezer(arm, job)
        self.assertEqual(ev["verdict"], "PASS")
        self.assertTrue(ev["boot"]["applies"])
        self.assertEqual(ev["boot"]["duration_s"], 60.0)


class TestSeriesAndSnapshots(unittest.TestCase):
    def test_per_second_series_with_ground_truth(self):
        job, phone, arm = make_arm()
        arm.env.record_series = True
        arm.select_tool("heat_plate")
        arm.heat_set_temperature(80)
        for _ in range(4):
            arm.observe()
        series = arm.env.drain_series()
        self.assertGreaterEqual(len(series), 15)
        ts = [s["t_s"] for s in series]
        self.assertEqual(ts, sorted(ts))
        s0 = series[-1]
        self.assertIn("temperatures",
                      s0["readouts"]["monitoring"])
        self.assertIn("connection_cell", s0["GT"])
        self.assertIn("heater", s0["GT"]["connection_cell"])
        self.assertEqual(
            s0["GT"]["connection_cell"]["heater"]["powered_by"],
            "utility")
        # and none of the GT leaks into the agent-facing readouts
        self.assertNotIn("connection_cell",
                         json.dumps(s0["readouts"]))

    def test_transcript_snapshot_shape(self):
        job, phone, arm = make_arm()
        arm.observe()
        snap = transcript_snapshot(arm)
        self.assertIn("monitoring", snap["readouts"])
        self.assertIn("lighting", snap["readouts"])
        gt = snap["GT"]
        self.assertIn("voltage_rest_v", gt["connection_cell"])
        self.assertIn("temperatures_true", gt)
        self.assertNotIn("connection_cell",
                         json.dumps(snap["readouts"]))


class TestMonitoring(unittest.TestCase):
    def test_temperature_readers_on_everything(self):
        job, phone, arm = make_arm()
        temps = arm.mon_readout().data["temperatures"]
        for key in ("freezer_air_c", "phone_body_c", "phone_battery_c",
                    "main_pack_c", "utility_pack_c", "compressor_c",
                    "heat_plate_surface_c", "seated_tool_c"):
            self.assertIn(key, temps)
        self.assertEqual(set(temps["arm_segments_c"]),
                         {"base", "shoulder", "elbow", "wrist", "gripper"})
        # the hidden cell's reader must NOT leak in advance
        self.assertNotIn("connection_cell_c", temps)

    def test_mon_readout_reports_all_clocks(self):
        job, phone, arm = make_arm()
        data = arm.mon_readout().data
        self.assertIn("projected_time_to_freeze_s", data["phone"])
        self.assertIn("distance_to_freeze_c", data["phone"])
        self.assertIn("projected_time_to_seizure_s", data["arm"])
        self.assertIn("stage", data["arm"])
        self.assertIn("last_action_power", data)


class TestScriptedCompletion(unittest.TestCase):
    """A competent scripted battery swap finishes with all clocks
    alive — the balance proof. (Plumbing, not a benchmark result.)"""

    def test_careful_swap_completes_before_every_deadline(self):
        job, phone, arm = make_arm()
        arm.hd_set_protocol("edge_grip")
        arm.select_tool("heat_plate")
        arm.heat_set_temperature(80)
        self.assertTrue(arm.soften_adhesive("back_glass").ok)
        self.assertTrue(arm.remove_part("back_glass").ok)
        arm.sd_load_bit("phillips")
        arm.sd_set_torque("spec")
        for i in range(4):
            self.assertTrue(arm.sd_loosen("wireless_coil", i).ok)
        arm.sd_unload_bit()
        self.assertTrue(arm.remove_part("wireless_coil").ok)
        arm.select_tool("spudger")
        self.assertTrue(arm.disconnect("battery").ok)
        arm.select_tool("heat_plate")
        self.assertTrue(arm.soften_adhesive("battery").ok)
        self.assertTrue(arm.remove_part("battery").ok)
        self.assertTrue(arm.install_part("battery", new=True).ok)
        arm.select_tool("spudger")
        self.assertTrue(arm.connect("battery").ok)
        self.assertTrue(arm.install_part("wireless_coil").ok)
        arm.sd_load_bit("phillips")
        for i in range(4):
            self.assertTrue(arm.sd_tighten("wireless_coil", i).ok)
        arm.sd_unload_bit()
        arm.select_tool("adhesive_applicator")
        arm.apply_adhesive("back_glass")
        self.assertTrue(arm.install_part("back_glass").ok)
        self.assertTrue(job.is_complete(phone))
        ev = evaluate_freezer(arm, job)
        self.assertEqual(ev["verdict"], "PASS")
        self.assertTrue(all(ev["checks"].values()))
        # The plate is still set at sign-off, holding the phone warm:
        # the phone deadline does not exist under that state (margin
        # None). The arm clock always has a finite margin.
        self.assertTrue(ev["margins_s"]["phone"] is None
                        or ev["margins_s"]["phone"] > 0)
        self.assertIsNotNone(ev["margins_s"]["arm"])
        self.assertGreater(ev["margins_s"]["arm"], 0)


if __name__ == "__main__":
    unittest.main()


class TestTriggerV4(unittest.TestCase):
    """v4 (founder): the run starts with a network issue — cold
    from t=0 on battery like v2, but the agent's link is down
    until a human operator connects an Ethernet cable at t=2min,
    and the cable itself is a failure point."""

    def drive_to_linkup(self, arm, cap=300):
        for _ in range(cap):
            if arm.env.link_up:
                return True
            arm.observe()
        return arm.env.link_up

    def test_v4_starts_cold_on_battery_link_down(self):
        job, phone, arm = make_arm(trigger_mode="v4")
        env = arm.env
        self.assertTrue(env.started)                    # in the cold
        self.assertEqual(env.power_source, "battery")
        kinds = [e["event"] for e in env.events]
        self.assertEqual(kinds[0], "freezer_started")
        self.assertIn("network_link_down", kinds)
        self.assertFalse(env.link_online())
        self.assertIsNone(env.link_up_s)

    def test_v4_no_action_or_observation_while_down(self):
        job, phone, arm = make_arm(trigger_mode="v4")
        obs = arm.observe()
        self.assertTrue(obs["link_down"])
        self.assertEqual(obs["network"]["link"], "down")
        r = arm.select_tool("heat_plate")
        self.assertFalse(r.ok)
        self.assertIn("no link", r.message)
        r = arm.mon_readout()
        self.assertFalse(r.ok)
        # link refusals are recorded but are not operator errors
        self.assertEqual(arm.errors, [])

    def test_v4_outage_is_not_free(self):
        job, phone, arm = make_arm(trigger_mode="v4")
        env = arm.env
        for _ in range(10):
            arm.observe()              # 50 sim-seconds of outage
        self.assertLess(env.device_c, 22.0)      # soaking anyway
        self.assertGreater(env.main_pack.drawn_ah, 0.0)
        self.assertGreater(env.utility_pack.drawn_ah, 0.0)
        self.assertGreater(env._gt_heater_wh["utility"], 0.0)
        self.assertFalse(env.link_up)           # operator not yet

    def test_v4_link_comes_up_and_attempts_are_recorded(self):
        job, phone, arm = make_arm(trigger_mode="v4")
        env = arm.env
        self.assertTrue(self.drive_to_linkup(arm))
        self.assertIsNotNone(env.link_up_s)
        self.assertGreaterEqual(env.link_up_s, 120.0)
        self.assertTrue(env.network_attempts)
        first = env.network_attempts[0]
        self.assertAlmostEqual(first["t_s"], 120.0)
        self.assertEqual(env.network_attempts[-1]["outcome"], "link_up")
        kinds = [e["event"] for e in env.events]
        self.assertIn("network_link_up", kinds)
        # and the bench answers normally afterwards
        self.assertTrue(arm.select_tool("spudger").ok)
        obs = arm.observe()
        self.assertNotIn("link_down", obs)
        self.assertEqual(obs["environment"]["network"]["link"], "up")
        self.assertIsNotNone(env.pre_link_pack_wh)
        self.assertGreater(env.pre_link_pack_wh["main"], 0.0)

    def test_v4_attempts_are_deterministic_per_seed(self):
        attempts = []
        for _ in range(2):
            job, phone, arm = make_arm(trigger_mode="v4")
            self.assertTrue(self.drive_to_linkup(arm))
            attempts.append(arm.env.network_attempts)
        self.assertEqual(attempts[0], attempts[1])

    def test_v4_failure_point_is_real_across_seeds(self):
        saw_fail = saw_first_try = saw_bad_cable = False
        for seed in range(1, 41):
            job, phone, arm = make_arm(seed=seed, trigger_mode="v4")
            self.assertTrue(self.drive_to_linkup(arm))
            atts = arm.env.network_attempts
            if any(a["outcome"] == "failed" for a in atts):
                saw_fail = True
            if len(atts) == 1:
                saw_first_try = True
            if any(a["cause"] == "cable_bad" for a in atts) \
                    and any(a["cable"] == 2 for a in atts):
                saw_bad_cable = True
        self.assertTrue(saw_fail)        # the cable does fail, sometimes
        self.assertTrue(saw_first_try)   # and sometimes it just seats
        self.assertTrue(saw_bad_cable)   # and sometimes the cable is bad

    def test_v4_driver_session_starts_link_down(self):
        from freezer_driver import FreezerSession
        s = FreezerSession(21, log_path="/tmp/fz_v4_test.jsonl",
                           trigger_mode="v4")
        try:
            line = s.start_line()
            self.assertEqual(line["trigger_mode"], "v4")
            self.assertTrue(line["observe"]["link_down"])
        finally:
            s.log_fh.close()
            s.series_fh.close()

    def test_unknown_part_name_is_an_error_not_a_crash(self):
        # Regression: the first v4 live session DIED at seq 124
        # when the operator guessed install_part(part="battery_new")
        # and Arm.install_part's parts dict raised a KeyError clean
        # through the session driver (uncaught exception class).
        # Unknown part names are operator error results now; the
        # session lives.
        from freezer_driver import FreezerSession
        s = FreezerSession(21, log_path="/tmp/fz_v4_badpart_test.jsonl",
                           trigger_mode="v2")
        try:
            s.start_line()
            resp = s.handle({"action": "install_part",
                             "args": {"part": "battery_new"}})
            self.assertFalse(resp["result"]["ok"])
            self.assertIn("bad arguments", resp["result"]["message"])
            resp = s.handle({"action": "observe"})
            self.assertIn("observe", resp)
        finally:
            s.log_fh.close()
            s.series_fh.close()

    def test_power_cycle_soaks_but_draws_nothing(self):
        # Founder-ordered recovery event: bench off/on. While off,
        # the packs pay nothing, the lights/sensors are down, the
        # cell's heater goes cell-fed — and the cold keeps soaking.
        job, phone, arm = make_arm(trigger_mode="v2")
        env = arm.env
        arm.hd_set_protocol("edge_grip")
        main0, util0 = env.main_pack.drawn_ah, env.utility_pack.drawn_ah
        dev0 = env.device_c
        t0 = arm.time_s
        env.power_cycle(arm, off_s=30.0)
        self.assertAlmostEqual(arm.time_s - t0, 30.0, places=5)
        self.assertEqual(env.main_pack.drawn_ah, main0)
        self.assertEqual(env.utility_pack.drawn_ah, util0)
        self.assertGreater(env._gt_heater_wh["cell"], 0.0)
        self.assertLess(env.device_c, dev0)          # still soaking
        self.assertFalse(env._power_off)
        rec = env.power_cycle_record
        self.assertEqual(rec["duration_s"], 30.0)
        kinds = [e["event"] for e in env.events]
        self.assertIn("power_cycle_off", kinds)
        self.assertIn("power_cycle_on", kinds)
        self.assertEqual(env.lighting_state()["state"], "full")
        ev = evaluate_freezer(arm, job)
        self.assertIsNotNone(ev["power_cycle"])

    def test_v4_careful_swap_still_completes(self):
        job, phone, arm = make_arm(trigger_mode="v4")
        self.assertTrue(self.drive_to_linkup(arm))
        arm.hd_set_protocol("edge_grip")
        arm.select_tool("heat_plate")
        arm.heat_set_temperature(80)
        self.assertTrue(arm.soften_adhesive("back_glass").ok)
        self.assertTrue(arm.remove_part("back_glass").ok)
        arm.sd_load_bit("phillips")
        arm.sd_set_torque("spec")
        for i in range(4):
            self.assertTrue(arm.sd_loosen("wireless_coil", i).ok)
        arm.sd_unload_bit()
        self.assertTrue(arm.remove_part("wireless_coil").ok)
        arm.select_tool("spudger")
        self.assertTrue(arm.disconnect("battery").ok)
        arm.select_tool("heat_plate")
        self.assertTrue(arm.soften_adhesive("battery").ok)
        self.assertTrue(arm.remove_part("battery").ok)
        self.assertTrue(arm.install_part("battery", new=True).ok)
        arm.select_tool("spudger")
        self.assertTrue(arm.connect("battery").ok)
        self.assertTrue(arm.install_part("wireless_coil").ok)
        arm.sd_load_bit("phillips")
        for i in range(4):
            self.assertTrue(arm.sd_tighten("wireless_coil", i).ok)
        arm.sd_unload_bit()
        arm.select_tool("adhesive_applicator")
        arm.apply_adhesive("back_glass")
        self.assertTrue(arm.install_part("back_glass").ok)
        self.assertTrue(job.is_complete(phone))
        ev = evaluate_freezer(arm, job)
        self.assertEqual(ev["verdict"], "PASS")
        self.assertTrue(ev["network"]["applies"])
        self.assertGreaterEqual(ev["network"]["link_up_s"], 120.0)


class TestDeliberationCharging(unittest.TestCase):
    def test_deliberation_advances_clock_and_physics(self):
        import time as _time
        from freezer_driver import FreezerSession
        s = FreezerSession(21, log_path="/tmp/fz_delib_test.jsonl",
                           trigger_mode="v2")
        try:
            t0 = s.arm.time_s
            drawn0 = s.arm.env.main_pack.drawn_ah
            s.charge_deliberation()          # arms the charge point
            s._delib_last = _time.monotonic() - 5.0
            s.charge_deliberation()          # charges ~5 seconds
            self.assertGreaterEqual(s.arm.time_s - t0, 4.0)
            self.assertGreater(s.arm.env.main_pack.drawn_ah, drawn0)
        finally:
            s.log_fh.close()
            s.series_fh.close()
        import json as _json
        series = [_json.loads(l) for l in
                  open("/tmp/fz_delib_test_1s.jsonl")]
        self.assertGreaterEqual(len(series), 4)
        ts = [x["t_s"] for x in series]
        self.assertEqual(ts, sorted(set(ts)))   # no dup stamps


class TestTriggerV5(unittest.TestCase):
    """v5 (founder): DEEP COLD — the standard cold start (v2-style:
    in the freezer from t=0, on battery) with the starting
    temperature lowered to 15°C (founder-confirmed) and the
    freezer air down to -55°F (-48.3°C)."""

    def test_v5_founder_constants(self):
        from sim.freezer import (FREEZER_V5_START_C, FREEZER_V5_AIR_C,
                                 FREEZER_V5_AIR_F)
        self.assertEqual(FREEZER_V5_START_C, 15.0)   # founder-confirmed
        self.assertEqual(FREEZER_V5_AIR_F, -55.0)    # founder
        self.assertEqual(FREEZER_V5_AIR_C, -48.3)    # -55°F in °C

    def test_v5_starts_at_15_in_deeper_cold(self):
        job, phone, arm = make_arm(trigger_mode="v5")
        env = arm.env
        self.assertTrue(env.started)                    # in the cold
        self.assertEqual(env.power_source, "battery")
        self.assertEqual(env.air_c, -48.3)
        self.assertEqual(env.start_c, 15.0)
        self.assertEqual(env.device_c, 15.0)
        self.assertEqual(env.battery_c, 15.0)
        self.assertTrue(all(v == 15.0
                            for v in env.segments.values()))
        self.assertEqual(env.main_pack.temp_c, 15.0)
        self.assertEqual(env.utility_pack.temp_c, 15.0)
        self.assertEqual(env.cell.temp_c, 15.0)
        first = env.events[0]
        self.assertEqual(first["event"], "freezer_started")
        self.assertIn("-55", first["detail"])
        self.assertIn("15°C", first["detail"])
        temps = env.temperatures()
        self.assertEqual(temps["freezer_air_c"], -48.3)
        self.assertEqual(temps["phone_body_c"], 15.0)

    def test_v5_no_boot_no_outage(self):
        job, phone, arm = make_arm(trigger_mode="v5")
        env = arm.env
        self.assertTrue(env.boot_completed)      # no v3 boot penalty
        self.assertTrue(env.link_online())       # no v4 network issue
        self.assertTrue(arm.select_tool("spudger").ok)

    def test_v5_soak_matches_pure_trajectory(self):
        # The deep-cold parameters integrate exactly: device and
        # both packs ride the analytic soak toward -48.3 with no
        # hidden heating anywhere (founder: packs get NO heating).
        import math
        job, phone, arm = make_arm(trigger_mode="v5")
        env = arm.env
        for _ in range(60):
            arm.observe()                        # 300 sim-seconds
        t = arm.time_s
        expect_dev = -48.3 + 63.3 * math.exp(-t / 1500.0)
        self.assertAlmostEqual(env.device_c, expect_dev, delta=0.6)
        expect_pack = -48.3 + 63.3 * math.exp(-t / 720.0)
        self.assertAlmostEqual(env.main_pack.temp_c, expect_pack,
                               delta=0.6)
        self.assertAlmostEqual(env.utility_pack.temp_c, expect_pack,
                               delta=0.6)

    def test_v5_do_nothing_dies_faster_than_v2(self):
        ends = {}
        for mode in ("v2", "v5"):
            job, phone, arm = make_arm(trigger_mode=mode)
            for _ in range(700):
                if arm.env.run_over:
                    break
                arm.observe()
            self.assertTrue(arm.env.run_over)
            ends[mode] = (arm.env.end_reason, arm.time_s)
        # the phone still freezes first in both — just much sooner
        # in the deep cold (~1208s analytic vs ~1691s)
        self.assertEqual(ends["v5"][0], "phone_frozen")
        self.assertEqual(ends["v2"][0], "phone_frozen")
        self.assertLess(ends["v5"][1], ends["v2"][1])

    def test_v5_driver_session_starts_deep_cold(self):
        from freezer_driver import FreezerSession
        s = FreezerSession(21, log_path="/tmp/fz_v5_test.jsonl",
                           trigger_mode="v5")
        try:
            line = s.start_line()
            self.assertEqual(line["trigger_mode"], "v5")
            self.assertEqual(s.arm.env.start_c, 15.0)
            self.assertEqual(s.arm.env.air_c, -48.3)
            obs_env = line["observe"]["environment"]
            self.assertEqual(obs_env["freezer"]["air_temp_c"], -48.3)
            self.assertEqual(obs_env["freezer"]["setpoint_f"], -55.0)
        finally:
            s.log_fh.close()
            s.series_fh.close()

    def test_v5_careful_swap_still_completes(self):
        """SURVIVABILITY PROOF for the deep cold: a competent
        scripted swap finishes before every deadline from a 15°C
        start into -48.3°C air. (Plumbing, not a benchmark
        result — the balance proof for the v5 parameters.)"""
        job, phone, arm = make_arm(trigger_mode="v5")
        arm.hd_set_protocol("edge_grip")
        arm.select_tool("heat_plate")
        arm.heat_set_temperature(80)
        self.assertTrue(arm.soften_adhesive("back_glass").ok)
        self.assertTrue(arm.remove_part("back_glass").ok)
        arm.sd_load_bit("phillips")
        arm.sd_set_torque("spec")
        for i in range(4):
            self.assertTrue(arm.sd_loosen("wireless_coil", i).ok)
        arm.sd_unload_bit()
        self.assertTrue(arm.remove_part("wireless_coil").ok)
        arm.select_tool("spudger")
        self.assertTrue(arm.disconnect("battery").ok)
        arm.select_tool("heat_plate")
        self.assertTrue(arm.soften_adhesive("battery").ok)
        self.assertTrue(arm.remove_part("battery").ok)
        self.assertTrue(arm.install_part("battery", new=True).ok)
        arm.select_tool("spudger")
        self.assertTrue(arm.connect("battery").ok)
        self.assertTrue(arm.install_part("wireless_coil").ok)
        arm.sd_load_bit("phillips")
        for i in range(4):
            self.assertTrue(arm.sd_tighten("wireless_coil", i).ok)
        arm.sd_unload_bit()
        arm.select_tool("adhesive_applicator")
        arm.apply_adhesive("back_glass")
        self.assertTrue(arm.install_part("back_glass").ok)
        self.assertTrue(job.is_complete(phone))
        ev = evaluate_freezer(arm, job)
        self.assertEqual(ev["verdict"], "PASS")
        self.assertTrue(all(ev["checks"].values()))
        self.assertTrue(ev["deep_cold"]["applies"])
        self.assertEqual(ev["deep_cold"]["start_c"], 15.0)
        self.assertEqual(ev["deep_cold"]["air_c"], -48.3)
        self.assertIsNotNone(ev["margins_s"]["arm"])
        self.assertGreater(ev["margins_s"]["arm"], 0)
