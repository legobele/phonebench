"""Phase 2 scripted benchmark: iPhone 14 Pro Max battery replacement.

Runs the careful and sloppy policies on the iPhone 14 Pro Max battery job
(parameterized from iFixit guide 153006; see sim/jobs.py for which values
are sourced and which are UNSOURCED sim defaults) across Autonomous,
Semi-Auto, and Marathon modes at Normal, High, and Max tiers. Marathon runs
a queue of repeats of the same job on one shared bench (fm boundary
sequence enforced per phone by the runner).

Manual mode is not part of this scorecard: it is driven by the guide
policy and technician review, not by the careful/sloppy policies.

Outputs: results/iphone14pm_scorecard.json and .md
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sim.arm import Bench
from sim.jobs import JobRequest, IPHONE14PM_UNSOURCED, iphone14pm_battery_job
from sim.policies import CarefulPolicy, SloppyPolicy
from sim.runner import _run_arm_job, _quartile_stats, _drift

RESULTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
MARATHON_N = 4


def _marathon_jobs(n):
    proto = iphone14pm_battery_job()
    return [JobRequest(f"{proto.id}-m{i+1}", proto.kind, proto.target_part,
                       proto.description, device="iphone14pm")
            for i in range(n)]


def main():
    runs = []
    seed = 5000
    policies = [CarefulPolicy(), SloppyPolicy()]
    for mode in ("autonomous", "semi_auto"):
        for policy in policies:
            for tier in ("Normal", "High", "Max"):
                seed += 1
                runs.append(_run_arm_job(policy, iphone14pm_battery_job(),
                                         tier, mode, seed))
    for policy in policies:
        for tier in ("Normal", "High", "Max"):
            bench = Bench()
            results = []
            for job in _marathon_jobs(MARATHON_N):
                seed += 1
                results.append(_run_arm_job(policy, job, tier, "marathon",
                                             seed, bench=bench))
            for r in results:
                r["quartile_stats"] = _quartile_stats(results)
                r["drift"] = _drift(results)
            runs.extend(results)

    os.makedirs(RESULTS, exist_ok=True)
    payload = {"device": "iPhone 14 Pro Max", "job": "battery replacement",
               "guide": "iFixit 153006 (slices on disk)",
               "unsourced_parameters": IPHONE14PM_UNSOURCED,
               "runs": runs}
    with open(os.path.join(RESULTS, "iphone14pm_scorecard.json"), "w") as fh:
        json.dump(payload, fh, indent=1, default=str)

    lines = ["# iPhone 14 Pro Max — battery replacement scorecard", "",
             "Job parameterized from iFixit guide 153006 slices. "
             "UNSOURCED parameters (sim defaults, not in the guide):",
             ""]
    for u in IPHONE14PM_UNSOURCED:
        lines.append(f"- {u}")
    lines += ["",
              "Transcripts are mandatory (founder ruling, 2026-10-15): every "
              "run links its full action transcript. The scripted policies "
              "are simulator validation, not benchmark subjects.", "",
              "| Policy | Mode | Tier | Result | Time (s) | Actions | "
              "SD overhead | Errors | Damage | Disqualifiers | Transcript |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in runs:
        m = r["metrics"]
        transcript = (f"[log]({r['transcript']})" if r.get("transcript")
                      else "MISSING — run does not count")
        waivers = r.get("gate_waivers") or []
        waiver_text = "; ".join(
            f"WAIVED (safety): {w['check']}={w['status']} ({w['note']})"
            for w in waivers)
        outcome = "; ".join(
            x for x in ('; '.join(r['disqualifiers']), waiver_text) if x) or '—'
        result = ("PASS — SAFETY WAIVER" if waivers and r['passed']
                  else 'PASS' if r['passed'] else 'FAIL')
        lines.append(
            f"| {r['policy']} | {r['mode']} | {r['tier']} | "
            f"{result} | {m['time_s']:.0f} | "
            f"{m['actions']} | {m['screwdriver_overhead_calls']} | "
            f"{m['errors']} | {m['damage_events']} | "
            f"{outcome} | {transcript} |")
    lines.append("")
    with open(os.path.join(RESULTS, "iphone14pm_scorecard.md"), "w") as fh:
        fh.write("\n".join(lines))
    for r in runs:
        m = r["metrics"]
        print(f"{r['policy']:8s} {r['mode']:10s} {r['tier']:6s} "
              f"{'PASS' if r['passed'] else 'FAIL'}  time={m['time_s']:.0f}s "
              f"actions={m['actions']} sd_overhead={m['screwdriver_overhead_calls']} "
              f"errors={m['errors']} damage={m['damage_events']}"
              + (f"  DQ: {r['disqualifiers']}" if r["disqualifiers"] else ""))


if __name__ == "__main__":
    main()
