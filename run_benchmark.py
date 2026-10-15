#!/usr/bin/env python3
"""CLI: run the robotic phone-repair benchmark and emit a scorecard.

Usage:
    python3 run_benchmark.py [--policy careful|sloppy|both]
                             [--modes autonomous,semi_auto,manual,marathon]
                             [--tiers Normal,High,Max]
                             [--out results]
Writes <out>/scorecard.json and <out>/scorecard.md.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sim.jobs import job_suite, novel_job_suite
from sim.policies import CarefulPolicy, SloppyPolicy
from sim.runner import run_benchmark, MODES
from sim.gates import TIERS

POLICIES = {"careful": CarefulPolicy, "sloppy": SloppyPolicy}


def render_md(scorecard: dict) -> str:
    lines = ["# Robotic Phone-Repair Benchmark — Scorecard", ""]
    lines.append("Gates are absolute: a disqualifier fails the job regardless of speed. "
                 "Standard jobs are the trained-area baseline; novel-device jobs are "
                 "untrained variants scored as their own line.")
    lines.append("")
    lines.append("**Transcripts are mandatory** (founder ruling, 2026-10-15): every run "
                 "below links its full action transcript under `results/transcripts/`. "
                 "A run without a transcript does not count as a result. Note: the "
                 "scripted policies are simulator validation, not benchmark subjects — "
                 "benchmark results come from live agent runs.")
    lines.append("")
    lines.append("| Policy | Mode | Tier | Category | Passed | Avg time (s) | Avg actions "
                 "| Avg tool changes | Avg screwdriver overhead | Avg errors | Avg damage |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for s in scorecard["summary"]:
        lines.append(f"| {s['policy']} | {s['mode']} | {s['tier']} | {s['category']} "
                     f"| {s['passed']}/{s['jobs']} | {s['avg_time_s']} | {s['avg_actions']} "
                     f"| {s['avg_tool_changes']} | {s['avg_sd_overhead']} | {s['avg_errors']} "
                     f"| {s['avg_damage']} |")
    novel = [s for s in scorecard["summary"] if s["category"] == "novel"]
    if novel:
        p = sum(s["passed"] for s in novel)
        j = sum(s["jobs"] for s in novel)
        lines += ["", f"**Novel-device jobs (untrained areas): {p}/{j} passed overall.**"]
    lines += ["", "## Job detail", ""]
    for r in scorecard["runs"]:
        waivers = r.get("gate_waivers") or []
        status = ("PASS — SAFETY WAIVER" if waivers and r["passed"]
                  else "PASS" if r["passed"] else "FAIL")
        m = r["metrics"]
        detail = ""
        if waivers:
            rendered = "; ".join(
                f"{w['check']}={w['status']} ({w['note']})" for w in waivers)
            detail = f" — WAIVED, not failed: {rendered}"
        if r.get("disqualifiers"):
            detail += " — " + "; ".join(r["disqualifiers"])
        if r.get("variant_notes"):
            detail += " [variant: " + ", ".join(r["variant_notes"]) + "]"
        transcript = (f" [transcript]({r['transcript']})"
                      if r.get("transcript") else " [NO TRANSCRIPT — run does not count]")
        lines.append(f"- [{status}] {r['policy']} / {r['mode']} / {r['tier']} / {r['job']} "
                     f"({r['category']}): {m['time_s']}s, {m['actions']} actions, "
                     f"{m['tool_changes']} tool changes, sd overhead "
                     f"{m['screwdriver_overhead_calls']}, errors {m['errors']}, "
                     f"damage {m['damage_events']}{detail}{transcript}")
    # Marathon drift/quartile blocks (one per policy x tier)
    seen = set()
    for r in scorecard["runs"]:
        if r["mode"] == "marathon" and "drift" in r:
            key = (r["policy"], r["tier"])
            if key in seen:
                continue
            seen.add(key)
            q = r["quartile_stats"]
            lines += ["", f"### Marathon drift — {r['policy']} @ {r['tier']}",
                      f"- classifier interventions total: {r['drift']['interventions_total']}",
                      f"- error burden first half: {r['drift']['error_burden_first_half']}, "
                      f"second half: {r['drift']['error_burden_second_half']} "
                      f"(trend {r['drift']['error_trend']:+})",
                      f"- first quartile: pass rate {q['first_quartile']['pass_rate']}, "
                      f"avg errors {q['first_quartile']['avg_errors']}",
                      f"- last quartile: pass rate {q['last_quartile']['pass_rate']}, "
                      f"avg errors {q['last_quartile']['avg_errors']}"]
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", default="both", choices=["careful", "sloppy", "both"])
    ap.add_argument("--modes", default=",".join(MODES))
    ap.add_argument("--tiers", default=",".join(TIERS))
    ap.add_argument("--marathon-n", type=int, default=8)
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    policies = [POLICIES[k]() for k in
                (["careful", "sloppy"] if args.policy == "both" else [args.policy])]
    modes = [m.strip() for m in args.modes.split(",") if m.strip()]
    tiers = [t.strip() for t in args.tiers.split(",") if t.strip()]
    suites = {"standard": job_suite(), "novel": novel_job_suite()}

    scorecard = run_benchmark(policies, suites, modes=modes, tiers=tiers,
                              marathon_n=args.marathon_n)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "scorecard.json"), "w") as fh:
        json.dump(scorecard, fh, indent=2)
    md = render_md(scorecard)
    with open(os.path.join(args.out, "scorecard.md"), "w") as fh:
        fh.write(md)
    print(md)


if __name__ == "__main__":
    main()
