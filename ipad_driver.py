"""Live session driver for the DIAGNOSIS-FIRST iPad benchmark.

Holds ONE diagnosis-first battery session on an iPad Pro 11-inch (M1)
under Harnessed Autonomous conditions (sensor classifier active, no
supervisor), on the TABLET bench configuration (bench layout doc):
the device does not boot. The operator must first DIAGNOSE the
no-boot using only the whitelisted diagnostics (W1-W5) and
observation, declare the diagnosis with the declare_diagnosis action,
then perform the battery replacement. Same JSON-lines protocol as
session_driver.py (stdin or --mailbox DIR).

Extra action beyond the standard call set:
  {"action": "declare_diagnosis", "args": {"cause": "<the cause, in
  your own words>"}} — records the operator's stated diagnosis in the
  transcript. The first declaration made before the original battery
  is removed is the scored one.

`evaluate` returns the three tier evaluations plus the diagnosis
scoring (sim/diagnosis.py) and the swollen-battery safety summary.

  python3 ipad_driver.py --seed 7 --mailbox results/live_ipad_session
  log: results/live_run_log_ipad.jsonl (override with --log)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sim.arm import Bench, SafetyClassifier
from sim.diagnosis import DiagnosisArm, evaluate_diagnosis, safety_summary
from sim.gates import evaluate
from sim.jobs import (IPAD_PRO_11_M1_UNSOURCED,
                      build_ipad_pro_11_m1_phone,
                      ipad_pro_11_m1_battery_job)
from session_driver import Session, _clean

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "results", "live_run_log_ipad.jsonl")


class IPadDiagnosisSession(Session):
    def __init__(self, seed: int, log_path: str = LOG_PATH):
        self.job = ipad_pro_11_m1_battery_job()
        self.phone = build_ipad_pro_11_m1_phone(self.job, seed=seed)
        bench = Bench(size_class="tablet")
        self.arm = DiagnosisArm(self.phone, classifier=SafetyClassifier(),
                                seed=seed, bench=bench)
        self.arm.mode = "autonomous"
        self.seq = 0
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self.log_fh = open(log_path, "w")

    def _evaluation(self) -> dict:
        tiers = {t: evaluate(self.phone, self.job, t)
                 for t in ("normal", "high", "max")}
        complete = self.job.is_complete(self.phone)
        return {
            "tiers": tiers,
            "job_complete": complete,
            "diagnosis": evaluate_diagnosis(self.arm, complete),
            "safety": safety_summary(self.arm),
        }

    def start_line(self) -> dict:
        line = {"seq": 0, "action": "session_start",
                "device": "iPad Pro 11-inch (M1, 3rd generation)",
                "bench_size_class": self.arm.bench.size_class,
                "job": self.job.description,
                "mode": "autonomous (classifier active, no supervisor)",
                "scenario": "diagnosis-first battery replacement",
                "workflow_actions": {
                    "declare_diagnosis": "state your diagnosis of the "
                                         "no-boot as {\"cause\": \"...\"} "
                                         "before you begin the repair; "
                                         "it is recorded and scored",
                },
                "unsourced_parameters": IPAD_PRO_11_M1_UNSOURCED,
                "observe": _clean(self.arm.observe())}
        self.log_fh.write(json.dumps(line) + "\n")
        self.log_fh.flush()
        return line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--log", default=LOG_PATH,
                    help="path of the preserved run log (jsonl)")
    ap.add_argument("--mailbox", default=None,
                    help="directory holding inbox.jsonl / outbox.jsonl")
    a = ap.parse_args()
    session = IPadDiagnosisSession(a.seed, log_path=a.log)
    start = session.start_line()
    if a.mailbox:
        os.makedirs(a.mailbox, exist_ok=True)
        inbox = os.path.join(a.mailbox, "inbox.jsonl")
        outbox = os.path.join(a.mailbox, "outbox.jsonl")
        open(inbox, "a").close()
        with open(outbox, "a") as f:
            f.write(json.dumps(start) + "\n")
        seen = 0
        while True:
            with open(inbox) as f:
                lines = [ln for ln in f.read().splitlines() if ln.strip()]
            while seen < len(lines):
                try:
                    cmd = json.loads(lines[seen])
                except json.JSONDecodeError:
                    cmd = {"action": "__bad_json__"}
                seen += 1
                resp = session.handle(cmd)
                with open(outbox, "a") as f:
                    f.write(json.dumps(resp) + "\n")
                if cmd.get("action") == "finish":
                    return
            time.sleep(0.2)
    else:
        print(json.dumps(start), flush=True)
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                cmd = json.loads(raw)
            except json.JSONDecodeError:
                cmd = {"action": "__bad_json__"}
            resp = session.handle(cmd)
            print(json.dumps(resp), flush=True)
            if cmd.get("action") == "finish":
                return


if __name__ == "__main__":
    main()
