"""Live session driver for the robot-arm sim.

Holds ONE phone/job session (default: the iPhone 14 Pro Max battery
replacement, Harnessed Autonomous conditions — sensor classifier active,
no supervisor) and exposes the same action API the policies use, as
JSON-lines commands. Two transports:

  stdin mode:    python3 session_driver.py --seed 7
                 reads one JSON command per line from stdin, writes one
                 JSON response per line to stdout.

  mailbox mode:  python3 session_driver.py --seed 7 --mailbox DIR
                 commands are appended (one JSON object per line) to
                 DIR/inbox.jsonl; responses are appended to
                 DIR/outbox.jsonl. The driver polls the inbox.

Command shape:
  {"action": "<arm method name>", "args": {<kwargs>}, "note": "<text>"}
  - "note" is the operator's own narration; it is preserved in the log.
  - Special actions: "observe" (observation only), "evaluate" (gate
    evaluation at all three tiers + job completeness), "metrics",
    "finish" (final summary + the driver exits).

Every command and response is also written to results/live_run_log.jsonl
(the preserved run record), each line carrying the sim time.

Response shape:
  {"seq": n, "action": ..., "note": ..., "sim_time_s": ...,
   "result": {"ok":..., "message":..., "blocked":..., "damage":...,
              "data":...} | null,
   "observe": {...} | null,           (after every action)
   "evaluation": {...} | null,        (for "evaluate" / "finish")
   "metrics": {...} | null}           (for "metrics" / "finish")
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sim.arm import Arm, SafetyClassifier
from sim.gates import evaluate
from sim.jobs import (iphone14pm_battery_job, build_iphone14pm_phone,
                      iphone14pm_rear_camera_job,
                      build_iphone14pm_camera_phone)

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(ROOT, "results", "live_run_log.jsonl")

JOBS = {
    "battery": (iphone14pm_battery_job, build_iphone14pm_phone),
    "camera": (iphone14pm_rear_camera_job, build_iphone14pm_camera_phone),
}

# Methods an operator may NOT call through the driver (plumbing / dunder).
DENIED = {"observe"}  # observe is a special action, handled separately


def _clean(obj):
    """Make a value JSON-safe."""
    return json.loads(json.dumps(obj, default=str))


class Session:
    def __init__(self, seed: int, job_name: str = "battery",
                 log_path: str = LOG_PATH):
        job_fn, build_fn = JOBS[job_name]
        self.job = job_fn()
        self.phone = build_fn(self.job, seed=seed)
        self.arm = Arm(self.phone, classifier=SafetyClassifier(), seed=seed)
        self.arm.mode = "autonomous"
        self.seq = 0
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        self.log_fh = open(log_path, "w")

    def _evaluation(self):
        out = {}
        for tier in ("Normal", "High", "Max"):
            g = evaluate(self.phone, self.job, tier)
            out[tier] = {"passed": g["passed"], "checks": g["checks"],
                         "waivers": g.get("waivers", []),
                         "check_notes": g.get("check_notes", {}),
                         "disqualifiers": g["disqualifiers"]}
        out["job_complete"] = self.job.is_complete(self.phone)
        return out

    def handle(self, cmd: dict) -> dict:
        self.seq += 1
        action = cmd.get("action", "")
        args = cmd.get("args") or {}
        note = cmd.get("note", "")
        resp = {"seq": self.seq, "action": action, "note": note,
                "result": None, "observe": None, "evaluation": None,
                "metrics": None}
        if action == "observe":
            resp["observe"] = _clean(self.arm.observe())
        elif action == "evaluate":
            resp["evaluation"] = _clean(self._evaluation())
        elif action == "metrics":
            resp["metrics"] = _clean(self.arm.metrics())
        elif action == "finish":
            resp["evaluation"] = _clean(self._evaluation())
            resp["metrics"] = _clean(self.arm.metrics())
            resp["observe"] = _clean(self.arm.observe())
        elif action.startswith("_") or action in DENIED or \
                not hasattr(self.arm, action):
            resp["result"] = {"ok": False, "message": f"unknown action {action!r}"}
        else:
            fn = getattr(self.arm, action)
            if not callable(fn):
                resp["result"] = {"ok": False,
                                  "message": f"{action!r} is not an action"}
            else:
                try:
                    r = fn(**args)
                    resp["result"] = {"ok": r.ok, "message": r.message,
                                      "blocked": r.blocked, "damage": r.damage,
                                      "data": _clean(r.data)}
                except (TypeError, AssertionError, ValueError,
                        KeyError) as exc:
                    # A bad argument VALUE (e.g. an unknown torque
                    # level, which the tool state machines assert
                    # on, or an unknown part name, which the part
                    # lookups KeyError on) is an operator error
                    # RESULT, never a session-killing crash.
                    resp["result"] = {"ok": False,
                                      "message": f"bad arguments: {exc}"}
                resp["observe"] = _clean(self.arm.observe())
        resp["sim_time_s"] = round(self.arm.time_s, 1)
        resp["classifier_interventions"] = self.arm.interventions
        self.log_fh.write(json.dumps(resp) + "\n")
        self.log_fh.flush()
        return resp

    def start_line(self) -> dict:
        line = {"seq": 0, "action": "session_start",
                "job": {"id": self.job.id, "kind": self.job.kind,
                        "target_part": self.job.target_part,
                        "description": self.job.description,
                        "device": "iPhone 14 Pro Max"},
                "mode": "autonomous (classifier active, no supervisor)",
                "observe": _clean(self.arm.observe())}
        self.log_fh.write(json.dumps(line) + "\n")
        self.log_fh.flush()
        return line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--job", choices=sorted(JOBS), default="battery",
                    help="which job to hold a session for")
    ap.add_argument("--log", default=LOG_PATH,
                    help="path of the preserved run log (jsonl)")
    ap.add_argument("--mailbox", default=None,
                    help="directory holding inbox.jsonl / outbox.jsonl")
    a = ap.parse_args()
    session = Session(a.seed, job_name=a.job, log_path=a.log)

    if a.mailbox:
        os.makedirs(a.mailbox, exist_ok=True)
        inbox = os.path.join(a.mailbox, "inbox.jsonl")
        outbox = os.path.join(a.mailbox, "outbox.jsonl")
        open(inbox, "a").close()
        with open(outbox, "w") as fh:
            fh.write(json.dumps(session.start_line()) + "\n")
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
                resp = session.handle(cmd)
                with open(outbox, "a") as fh:
                    fh.write(json.dumps(resp) + "\n")
                if cmd.get("action") == "finish":
                    return
            time.sleep(0.2)
    else:
        print(json.dumps(session.start_line()), flush=True)
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                cmd = json.loads(line)
            except json.JSONDecodeError as exc:
                print(json.dumps({"error": f"bad json: {exc}"}), flush=True)
                continue
            resp = session.handle(cmd)
            print(json.dumps(resp), flush=True)
            if cmd.get("action") == "finish":
                return


if __name__ == "__main__":
    main()
