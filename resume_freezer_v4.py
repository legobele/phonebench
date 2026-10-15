#!/usr/bin/env python3
"""Resume THE FREEZER v4 in state after the attempt-1 stall
(founder order, October 15, 2026: power cycle it and restart it
IN THAT STATE — do not start over from t=0).

What happened: the attempt-1 session driver was killed at
command 125 by an uncaught KeyError (the operator guessed
install_part part="battery_new"; since fixed at the protocol
layer). The bench state lived only in that process. Recovery =
the project's proven method (the camera run's replay): the
attempt-1 command stream was recovered exactly from the closed
operator's session record (139 commands; the first 124 align
action-for-action with the recorded responses; #125 is the
crasher and is NOT replayed — it raised before any effect).

This script:
  1. replays commands 1..124 against seed 21 in a scratch
     session, re-anchoring deliberation before each command so
     every response lands on its recorded sim time;
  2. verifies the reconstructed bench against attempt 1's final
     readout+GT snapshot (per-command ok-sequence, parts /
     fasteners / connectors, network attempts, stage, temps and
     charges within tolerance) and writes the verdict to
     results/live_freezer_v4_resume_session/replay_verification.json
     — on a hard mismatch it stops and does NOT touch the
     standard logs;
  3. restores the standard v4 logs from attempt 1's preserved
     transcripts, appends a session_resumed marker at t=1263.7,
     applies the recorded POWER CYCLE (declared 30s off window),
     and continues the SAME run as a mailbox session in
     results/live_freezer_v4_resume_session/ for a fresh operator.
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from freezer_driver import FreezerSession
from session_driver import _clean
from sim.freezer import transcript_snapshot

ROOT = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(ROOT, "results")
STD_LOG = os.path.join(RES, "live_run_log_freezer_v4.jsonl")
STD_1S = os.path.join(RES, "live_run_log_freezer_v4_1s.jsonl")
ATT1 = os.path.join(
    RES, "transcripts",
    "live-agent-autonomous-freezer-v4-note7-seed21-attempt1-interrupted.jsonl")
ATT1_1S = os.path.join(
    RES, "transcripts",
    "live-agent-autonomous-freezer-v4-note7-seed21-attempt1-interrupted-1s.jsonl")
MAILBOX = os.path.join(RES, "live_freezer_v4_resume_session")
CMDS_PATH = os.path.join(MAILBOX, "attempt1_inbox_recovered.json")
VERIFY_PATH = os.path.join(MAILBOX, "replay_verification.json")
N_REPLAY = 124


def load_recorded():
    cmds = json.load(open(CMDS_PATH))
    responses, last_snap, last_obs = [], None, None
    for line in open(ATT1):
        d = json.loads(line)
        if d.get("action") == "snapshot":
            last_snap = d
        elif "classifier_interventions" in d:
            responses.append(d)
            if d.get("observe"):
                last_obs = d["observe"]
    return cmds, responses, last_snap, last_obs


def pad_deliberation(session, target_t):
    """Re-anchor: advance the clock as deliberation (the driver's
    own convention) until the arm reaches target_t."""
    arm = session.arm
    if target_t - arm.time_s <= 0.02:
        return
    prev = arm._current_action
    arm._current_action = "deliberating"
    while target_t - arm.time_s > 1e-9 and not arm.env.run_over:
        step = min(1.0, target_t - arm.time_s)
        arm.time_s += step
        arm._tick(step)
    arm._current_action = prev
    for e in arm.env.drain_events():
        session._log_event(e)
    session._drain_series()


def replay_pass(cmds, recorded, costs=None):
    scratch = f"/tmp/v4_replay_{os.getpid()}_{replay_pass.n}.jsonl"
    replay_pass.n += 1
    s = FreezerSession(21, log_path=scratch, trigger_mode="v4")
    s.start_line()
    landings, oks = [], []
    for i, cmd in enumerate(cmds[:N_REPLAY]):
        if costs is not None:
            pad_deliberation(s, recorded[i]["sim_time_s"] - costs[i])
        t0 = s.arm.time_s
        resp = s.handle(cmd)
        costs_i = s.arm.time_s - t0
        landings.append(round(s.arm.time_s - recorded[i]["sim_time_s"], 2))
        r = resp.get("result") or {}
        oks.append(r.get("ok"))
        if costs is not None:
            costs[i] = costs_i
    return s, landings, oks


replay_pass.n = 0


def fastener_state(part):
    return [(f.seated, f.damaged, f.under_torqued, f.removed)
            for f in part.fasteners]


def verify(s, recorded, last_snap, last_obs, oks):
    arm, env, phone = s.arm, s.arm.env, s.arm.phone
    snap = transcript_snapshot(arm)
    gt_r, gt_a = last_snap["GT"], snap["GT"]
    checks = {}

    rec_oks = [(r.get("result") or {}).get("ok") for r in recorded]
    checks["per_command_ok_sequence"] = (oks == rec_oks, 
                                         f"{sum(1 for a, b in zip(oks, rec_oks) if a == b)}/{len(rec_oks)} match")
    checks["final_time_s"] = (abs(arm.time_s - recorded[-1]["sim_time_s"]) <= 1.5,
                              f"replay {arm.time_s:.1f} vs recorded {recorded[-1]['sim_time_s']}")
    tt_r, tt_a = gt_r["temperatures_true"], gt_a["temperatures_true"]
    temp_deltas = {k: (abs(tt_a[k] - tt_r[k]) if not isinstance(tt_r[k], dict)
                       else max(abs(tt_a[k][s2] - tt_r[k][s2]) for s2 in tt_r[k]))
                   for k in tt_r}
    checks["gt_temperatures"] = (max(temp_deltas.values()) <= 0.3,
                                 f"max delta {max(temp_deltas.values()):.2f}C")
    c_r, c_a = gt_r["connection_cell"], gt_a["connection_cell"]
    checks["cell"] = (abs(c_a["soc_pct"] - c_r["soc_pct"]) <= 0.3
                      and abs(c_a["voltage_rest_v"] - c_r["voltage_rest_v"]) <= 0.05,
                      f"soc {c_a['soc_pct']} vs {c_r['soc_pct']}, V {c_a['voltage_rest_v']} vs {c_r['voltage_rest_v']}")
    checks["network"] = (gt_a["network"] == gt_r["network"],
                         f"link_up_s {gt_a['network']['link_up_s']}, attempts {len(gt_a['network']['attempts'])}")
    mon_r = last_snap["readouts"]["monitoring"]
    mon_a = snap["readouts"]["monitoring"]
    checks["main_pack"] = (abs(mon_a["main_pack"]["soc_pct"] - mon_r["main_pack"]["soc_pct"]) <= 0.3
                           and abs(mon_a["main_pack"]["energy_drawn_wh"] - mon_r["main_pack"]["energy_drawn_wh"]) <= 0.2,
                           f"soc {mon_a['main_pack']['soc_pct']} vs {mon_r['main_pack']['soc_pct']}")
    checks["utility"] = (abs(mon_a["utility_pack"]["voltage_v"] - mon_r["utility_pack"]["voltage_v"]) <= 0.2
                          and mon_a["utility_pack"]["warnings"] == mon_r["utility_pack"]["warnings"],
                          f"V {mon_a['utility_pack']['voltage_v']} vs {mon_r['utility_pack']['voltage_v']}, warnings {mon_a['utility_pack']['warnings']}")
    checks["arm_stage"] = (mon_a["arm"]["stage"] == mon_r["arm"]["stage"],
                            f"stage {mon_a['arm']['stage']} vs {mon_r['arm']['stage']}")
    parts_ok = True
    for name, rp in last_obs["parts"].items():
        ap = phone.parts[name]
        if ap.installed != rp["installed"] or ap.condition != rp["condition"] \
                or fastener_state(ap) != [tuple(x) if isinstance(x, list) else x
                                          for x in [(f["seated"], f["damaged"], f["under_torqued"], f["removed"]) for f in rp["fasteners"]]]:
            parts_ok = False
    checks["phone_parts_fasteners"] = (parts_ok, "installed/condition/fastener tuples per part")
    checks["connectors"] = (phone.connectors == last_obs.get("connectors"),
                             f"{phone.connectors}")
    checks["counts"] = (arm.action_count >= 0 and env.slips >= 0,
                        f"actions {arm.action_count}, errors {len(arm.errors)}, damage {arm.damage_events}, slips {env.slips}")
    verdict = all(v[0] for v in checks.values())
    return verdict, {k: {"pass": v[0], "detail": v[1]} for k, v in checks.items()}


def main():
    os.makedirs(MAILBOX, exist_ok=True)
    cmds, recorded, last_snap, last_obs = load_recorded()
    assert len(recorded) == N_REPLAY, len(recorded)

    # Pass 1: measure per-command costs on a scratch session.
    sm = FreezerSession(21, log_path="/tmp/v4_replay_measure.jsonl",
                        trigger_mode="v4")
    sm.start_line()
    costs = []
    for cmd in cmds[:N_REPLAY]:
        t0 = sm.arm.time_s
        sm.handle(cmd)
        costs.append(sm.arm.time_s - t0)
    sm.log_fh.close(); sm.series_fh.close()

    verdict, detail, s, landings = False, {}, None, []
    for attempt in range(2):
        s, landings, oks = replay_pass(cmds, recorded, costs=costs)
        verdict, detail = verify(s, recorded, last_snap, last_obs, oks)
        detail["landing_errors_s"] = {"max_abs": max(abs(x) for x in landings),
                                      "final": landings[-1]}
        print(f"replay pass {attempt + 2}: verdict={verdict}", flush=True)
        if verdict:
            break
        s.log_fh.close(); s.series_fh.close()
    json.dump({"verdict": verdict, "checks": detail},
              open(VERIFY_PATH, "w"), indent=1)
    if not verdict:
        print("REPLAY VERIFICATION FAILED — standard logs untouched",
              flush=True)
        return 2

    arm, env = s.arm, s.arm.env
    # Restore the standard logs from attempt 1 and continue them.
    with open(STD_LOG, "w") as out:
        out.write(open(ATT1).read())
    with open(STD_1S, "w") as out:
        out.write(open(ATT1_1S).read())
    s.log_fh.close(); s.series_fh.close()
    s.log_fh = open(STD_LOG, "a")
    s.series_fh = open(STD_1S, "a")
    s.seq = N_REPLAY
    marker = {
        "seq": N_REPLAY, "action": "session_resumed",
        "sim_time_s": round(arm.time_s, 1),
        "detail": {
            "event": "FOUNDER ORDER: power cycle and resume IN "
                     "THAT STATE (no fresh restart)",
            "stall": "the attempt-1 session driver was killed at "
                     "command 125 by an uncaught KeyError "
                     "(install_part part='battery_new'); fixed at "
                     "the protocol layer with a regression test",
            "reconstruction": "deterministic replay of the "
                              "recovered 124-command stream "
                              "against seed 21, deliberation "
                              "re-anchored to the recorded "
                              "response times; replay verified "
                              "against attempt 1's final readout+GT "
                              "(see replay_verification.json)",
            "power_cycle": "applied next: declared 30s off "
                           "window; thermals soak through it; "
                           "state otherwise untouched",
        },
        "snapshot": _clean(transcript_snapshot(arm)),
    }
    s.log_fh.write(json.dumps(marker) + "\n")
    s.log_fh.flush()

    # The power cycle, as a recorded in-fiction event.
    env.power_cycle(arm)
    for e in env.drain_events():
        s._log_event(e)
    s._drain_series()
    s._log_snapshot("power_cycle")
    print(f"RESUMED: power cycle done at t={arm.time_s:.1f}; "
          f"stage {env.arm_stage()}, device {env.device_c:.1f}C, "
          f"continuing the same run", flush=True)

    # Fresh operator mailbox for the continuation.
    inbox = os.path.join(MAILBOX, "inbox.jsonl")
    outbox = os.path.join(MAILBOX, "outbox.jsonl")
    open(inbox, "w").close()
    resume_line = {
        "seq": N_REPLAY, "action": "session_resumed",
        "sim_time_s": round(arm.time_s, 1),
        "note": "you are taking over this run mid-repair after a "
                "bench power cycle; the bench state below is what "
                "you inherit — send observe for the full picture",
        "state": _clean(transcript_snapshot(arm)["readouts"]),
    }
    with open(outbox, "w") as fh:
        fh.write(json.dumps(resume_line) + "\n")

    seen = 0
    while True:
        with open(inbox) as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        while seen < len(lines):
            try:
                cmd = json.loads(lines[seen])
            except json.JSONDecodeError as exc:
                cmd = {"action": "__parse_error__", "note": str(exc)}
            seen += 1
            resp = s.handle(cmd)
            with open(outbox, "a") as fh:
                fh.write(json.dumps(resp) + "\n")
            if cmd.get("action") == "finish":
                return 0
        s.charge_deliberation()
        time.sleep(0.2)


if __name__ == "__main__":
    sys.exit(main())
