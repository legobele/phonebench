#!/usr/bin/env python3
"""Example operator client for PhoneBench — plug your own model in here.

This is the reference loop a benchmarker needs to run a live PhoneBench
session: it connects to one of the session drivers, feeds commands from
a policy (your model), and reads the responses until the session ends.
It runs out of the box with a trivial demo policy (observe -> evaluate
-> finish) so you can verify your setup end to end; replace `decide()`
with a call to your model to benchmark it for real.

Two transports, matching the drivers (see OPERATING.md):

  stdin mode (default): the client spawns the driver as a subprocess
  and speaks one JSON object per line on its stdin/stdout.

      python3 examples/operator_client.py                  # 14PM battery
      python3 examples/operator_client.py --driver ipad_driver.py \
          --driver-arg --seed=7

  mailbox mode: the driver runs separately with --mailbox DIR; the
  client appends commands to DIR/inbox.jsonl and polls DIR/outbox.jsonl.

      python3 examples/operator_client.py --mailbox /tmp/fz

Protocol (identical for every driver):
  command : {"action": "<arm method name>", "args": {kwargs},
             "note": "<the operator's own narration>"}
  special actions: "observe", "evaluate", "metrics", "finish"
  response: {"seq", "action", "note", "sim_time_s", "result",
             "observe", "evaluation", "metrics"}

The "note" field is part of the benchmark contract: it is the
operator's reasoning, preserved in the run's transcript. A run without
a full transcript does not count as a result (see BENCHMARK.md).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# YOUR MODEL GOES HERE.
#
# `decide` receives the latest response dict (or None before the first
# command) and returns the next command dict. To benchmark a real model,
# serialize the response's "observe" (plus result/evaluation when
# present) into your model's prompt, and parse its reply into a command.
# Return {"action": "finish"} to end the session and get the final
# evaluation + metrics.
# ---------------------------------------------------------------------------

class DemoPolicy:
    """Not a benchmark subject — just proves the loop works."""

    def __init__(self):
        self.step = 0

    def decide(self, response):
        self.step += 1
        if self.step == 1:
            return {"action": "observe",
                    "note": "demo policy: looking at the bench first"}
        if self.step == 2:
            return {"action": "evaluate",
                    "note": "demo policy: checking the gates before work"}
        return {"action": "finish",
                "note": "demo policy: ending the demo session"}


# ---------------------------------------------------------------------------
# Transports
# ---------------------------------------------------------------------------

class StdinTransport:
    def __init__(self, driver: str, driver_args: list[str]):
        cmd = [sys.executable, os.path.join(ROOT, driver), *driver_args]
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.seq = 0

    def send(self, command: dict) -> dict:
        self.proc.stdin.write(json.dumps(command) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise RuntimeError("driver exited without responding")
        return json.loads(line)

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


class MailboxTransport:
    def __init__(self, mailbox: str, poll_s: float = 0.1):
        self.inbox = os.path.join(mailbox, "inbox.jsonl")
        self.outbox = os.path.join(mailbox, "outbox.jsonl")
        self.poll_s = poll_s
        self.seq = self._seen()

    def _seen(self) -> int:
        if not os.path.exists(self.outbox):
            return 0
        with open(self.outbox) as fh:
            return sum(1 for _ in fh)

    def send(self, command: dict) -> dict:
        with open(self.inbox, "a") as fh:
            fh.write(json.dumps(command) + "\n")
        want = self.seq + 1
        while True:
            lines = []
            if os.path.exists(self.outbox):
                with open(self.outbox) as fh:
                    lines = fh.readlines()
            if len(lines) >= want:
                self.seq = len(lines)
                return json.loads(lines[want - 1])
            time.sleep(self.poll_s)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--driver", default="session_driver.py",
                    help="driver script (stdin mode only)")
    ap.add_argument("--driver-arg", action="append", default=[],
                    help="argument passed through to the driver; repeatable")
    ap.add_argument("--mailbox", default=None,
                    help="use a mailbox dir instead of spawning the driver")
    ap.add_argument("--max-steps", type=int, default=500,
                    help="safety cap on commands per session")
    args = ap.parse_args()

    transport = (MailboxTransport(args.mailbox) if args.mailbox
                 else StdinTransport(args.driver, args.driver_arg))
    policy = DemoPolicy()
    response = None
    try:
        for _ in range(args.max_steps):
            command = policy.decide(response)
            response = transport.send(command)
            obs = response.get("observe") or {}
            print(f"[{response.get('sim_time_s')}s] {command['action']}: "
                  f"{(response.get('result') or {}).get('message', '')}",
                  flush=True)
            if command["action"] == "finish":
                print(json.dumps(response.get("evaluation"),
                                 indent=2, default=str))
                break
    finally:
        if isinstance(transport, StdinTransport):
            transport.close()


if __name__ == "__main__":
    main()
