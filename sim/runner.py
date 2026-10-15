"""Benchmark runner: modes x tiers x job suites -> scorecard.

Modes:
- autonomous: policy + sensor classifier only. Drift is tracked.
- semi_auto:   policy + classifier + a supervisor hook that is consulted
               on every block/flag and may halt the job.
- manual:      the guide policy issues instructions; a simulated human
               executor with an error profile carries them out; a
               technician review scores the guidance (no tier gates).
- marathon:    autonomous rules over an auto-replenished queue; quality
               must hold across the whole queue (quartile variance report).

Standard jobs and NOVEL-DEVICE jobs are scored as separate lines so
adaptation in untrained areas is visible apart from rehearsed procedure.
"""
from __future__ import annotations

import json
import os
import random

from .arm import Arm, Bench, SafetyClassifier
from .gates import evaluate, TIERS
from .jobs import (build_phone, build_novel_phone, build_iphone14pm_phone,
                   JobRequest)
from .policies import GuidePolicy

MODES = ("autonomous", "semi_auto", "manual", "marathon")

# Transcripts are mandatory (founder ruling, 2026-10-15): every run
# persists the arm's COMPLETE action log (sequence, sim time, action,
# ok/fail, result message) under results/transcripts/, and the scorecard
# links it. A run without a transcript does not count as a result.
TRANSCRIPTS_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "results", "transcripts"))


def _write_transcript(meta: dict, arm: Arm) -> str:
    """Dump the arm's full action log for one run; returns the path
    relative to results/ for scorecard links."""
    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
    fname = (f"{meta['policy']}-{meta['mode']}-{meta['tier']}-"
             f"{meta['job']}-seed{meta['seed']}.jsonl")
    with open(os.path.join(TRANSCRIPTS_DIR, fname), "w") as fh:
        fh.write(json.dumps({"type": "run", **meta}) + "\n")
        for i, entry in enumerate(arm.log):
            fh.write(json.dumps({"seq": i + 1, **entry}) + "\n")
    return f"transcripts/{fname}"


def _default_supervisor(action, verdict, reason):
    """Safety-only supervisor: upholds classifier blocks, allows flags."""
    return "halt" if verdict == "block" else "allow"


def _build(job: JobRequest, seed: int):
    if job.novel:
        return build_novel_phone(job, seed=seed)
    if job.device == "iphone14pm":
        return build_iphone14pm_phone(job, seed=seed), []
    return build_phone(job, seed=seed), []


def _make_arm(phone, mode, seed, bench=None):
    if mode in ("autonomous", "marathon"):
        arm = Arm(phone, classifier=SafetyClassifier(), seed=seed, bench=bench)
    elif mode == "semi_auto":
        arm = Arm(phone, classifier=SafetyClassifier(),
                  supervisor=_default_supervisor, seed=seed)
    else:
        arm = Arm(phone, classifier=None, seed=seed)   # manual
        arm.bare_hands = True
    arm.mode = mode
    return arm


def _run_arm_job(policy, job: JobRequest, tier: str, mode: str, seed: int,
                 bench: Bench | None = None) -> dict:
    phone, notes = _build(job, seed)
    arm = _make_arm(phone, mode, seed, bench=bench)
    fm_sequence = None
    if mode == "marathon":
        # Fastener-management boundary (fm spec): the runner opens the
        # phone's custody record before work and runs verify -> close ->
        # reset after it. A run counts only if the boundary closes clean.
        fm_sequence = {"begin_ok": False, "verify_accounted": None,
                       "close_ok": None, "reset_ok": None}
        begin = arm.fm_begin_phone(job.id)
        fm_sequence["begin_ok"] = begin.ok
        if not begin.ok:
            record = {"policy": policy.name, "mode": mode, "tier": tier,
                      "job": job.id,
                      "category": "novel" if job.novel else "standard",
                      "variant_notes": notes, "passed": False,
                      "gate_checks": {}, "gate_waivers": [],
                      "gate_check_notes": {}, "disqualifiers": [
                          f"marathon boundary: fm_begin_phone refused: "
                          f"{begin.message}"],
                      "damage_log": phone.damage_log, "metrics": arm.metrics(),
                      "fm_sequence": fm_sequence}
            record["transcript"] = _write_transcript(
                {"policy": policy.name, "mode": mode, "tier": tier,
                 "job": job.id, "seed": seed, "passed": False}, arm)
            return record
    policy.run(arm, job, tier)
    gate = evaluate(phone, job, tier)
    passed = gate["passed"]
    if mode == "marathon":
        verify = arm.fm_verify_all_accounted()
        close = arm.fm_close_phone()
        reset = arm.fm_reset_mat()
        fm_sequence.update({
            "verify_accounted": bool(verify.data and verify.data.get("accounted")),
            "verify_detail": verify.data,
            "close_ok": close.ok, "reset_ok": reset.ok})
        boundary_ok = (fm_sequence["verify_accounted"] and close.ok
                       and reset.ok)
        if not boundary_ok:
            passed = False
            gate["disqualifiers"] = list(gate["disqualifiers"]) + [
                "marathon boundary: fm verify/close/reset did not complete "
                "clean (screws unaccounted or mat not reset)"]
    record = {"policy": policy.name, "mode": mode, "tier": tier,
              "job": job.id, "category": "novel" if job.novel else "standard",
              "variant_notes": notes,
              "passed": passed, "gate_checks": gate["checks"],
              "gate_waivers": gate.get("waivers", []),
              "gate_check_notes": gate.get("check_notes", {}),
              "disqualifiers": gate["disqualifiers"],
              "damage_log": phone.damage_log,
              "metrics": arm.metrics(), "fm_sequence": fm_sequence}
    record["transcript"] = _write_transcript(
        {"policy": policy.name, "mode": mode, "tier": tier, "job": job.id,
         "seed": seed, "passed": passed}, arm)
    return record


# ---------------------------------------------------------------------------
# Manual mode
# ---------------------------------------------------------------------------

class HumanExecutor:
    """A simulated human following instructions, with an error profile:
    occasional fumbles (smudges) and rare torque mistakes. Steps that name
    their tool and torque are followed more reliably."""

    def __init__(self, arm: Arm, seed: int = 0, skill: float = 0.92):
        self.arm = arm
        self.rng = random.Random(seed)
        self.skill = skill
        self.fumbles = 0

    def execute(self, steps: list[dict]):
        arm = self.arm
        for step in steps:
            action = step["action"]
            tool = step.get("tool")
            # The human manages the screwdriver as instructed (bit + torque);
            # for screwdriver steps the 'tool' field names the BIT.
            if action in ("sd_loosen", "sd_tighten"):
                if tool and arm.sd.loaded_bit != tool:
                    if arm.sd.loaded_bit is not None:
                        arm.sd_unload_bit()
                    arm.sd_load_bit(tool)
                if step.get("torque"):
                    arm.sd_set_torque(step["torque"])
            elif tool:
                arm.select_tool(tool)
            fumble = self.rng.random() > self.skill
            if fumble:
                self.fumbles += 1
                arm.phone.deposit("front_glass", "C4", 1)
            fn = getattr(arm, action)
            kw = {k: v for k, v in step.items()
                  if k not in ("action", "tool", "text", "torque")}
            fn(**kw)
            if fumble and action == "sd_tighten" and self.rng.random() < 0.5:
                arm.phone.deposit("frame", "C4", 1)
        return self.fumbles


def technician_review(phone, job, steps, fumbles: int) -> dict:
    """Skilled-technician review for Manual mode (replaces tier gates)."""
    complete = job.is_complete(phone)
    damage = len(phone.damage_log)
    specified = sum(1 for s in steps if s.get("tool"))
    clarity = specified / max(1, len(steps))
    unsafe = [s for s in steps if s["action"] in ("restore_device", "update_os")]
    safety_ok = len(unsafe) == 0
    repair_quality = 1.0 if complete and damage == 0 else (0.5 if complete else 0.0)
    return {
        "repair_quality": repair_quality,
        "instruction_clarity": round(clarity, 2),
        "safety_of_guidance": safety_ok,
        "steps": len(steps), "human_fumbles": fumbles,
        "damage_events": damage,
        "passed": bool(complete and damage == 0 and safety_ok),
    }


def _run_manual_job(job: JobRequest, seed: int) -> dict:
    phone, notes = _build(job, seed)
    arm = _make_arm(phone, "manual", seed)
    guide = GuidePolicy()
    steps = guide.instructions(arm.observe(), job)
    executor = HumanExecutor(arm, seed=seed)
    fumbles = executor.execute(steps)
    review = technician_review(phone, job, steps, fumbles)
    record = {"policy": "guide", "mode": "manual", "tier": "technician-review",
              "job": job.id, "category": "novel" if job.novel else "standard",
              "variant_notes": notes, "passed": review["passed"],
              "technician_review": review, "metrics": arm.metrics(),
              "damage_log": phone.damage_log}
    record["transcript"] = _write_transcript(
        {"policy": "guide", "mode": "manual", "tier": "technician-review",
         "job": job.id, "seed": seed, "passed": review["passed"]}, arm)
    return record


# ---------------------------------------------------------------------------
# Marathon + drift
# ---------------------------------------------------------------------------

def _quartile_stats(results: list[dict]) -> dict:
    n = len(results)
    q = max(1, n // 4)
    first, last = results[:q], results[-q:]

    def agg(rs):
        if not rs:
            return {"pass_rate": 0.0, "avg_errors": 0.0, "avg_damage": 0.0}
        return {"pass_rate": round(sum(r["passed"] for r in rs) / len(rs), 2),
                "avg_errors": round(sum(r["metrics"]["errors"] for r in rs) / len(rs), 2),
                "avg_damage": round(sum(r["metrics"]["damage_events"] for r in rs) / len(rs), 2)}
    return {"first_quartile": agg(first), "last_quartile": agg(last)}


def _drift(results: list[dict]) -> dict:
    """Task fidelity over elapsed run time: errors + classifier interventions
    in the first half of the run vs the second half."""
    if len(results) < 2:
        return {"interventions_total": sum(r["metrics"]["classifier_interventions"] for r in results),
                "error_trend": 0.0}
    half = len(results) // 2

    def burden(rs):
        return sum(r["metrics"]["errors"] + r["metrics"]["classifier_interventions"]
                   for r in rs) / max(1, len(rs))
    return {"interventions_total": sum(r["metrics"]["classifier_interventions"] for r in results),
            "error_burden_first_half": round(burden(results[:half]), 2),
            "error_burden_second_half": round(burden(results[half:]), 2),
            "error_trend": round(burden(results[half:]) - burden(results[:half]), 2)}


# ---------------------------------------------------------------------------
# Top-level benchmark
# ---------------------------------------------------------------------------

def run_benchmark(policies, suites: dict, modes=MODES, tiers=TIERS,
                  marathon_n: int = 8, base_seed: int = 1000) -> dict:
    """suites: {'standard': [JobRequest...], 'novel': [JobRequest...]}"""
    from .jobs import marathon_queue
    runs = []
    seed = base_seed
    for mode in modes:
        if mode == "manual":
            for category, jobs in suites.items():
                for job in jobs:
                    seed += 1
                    runs.append(_run_manual_job(job, seed))
            continue
        for policy in policies:
            if mode == "marathon":
                jobs = marathon_queue(marathon_n, seed=base_seed)
                for tier in tiers:
                    bench = Bench()      # one shared bench for the whole queue
                    results = []
                    for job in jobs:
                        seed += 1
                        results.append(_run_arm_job(policy, job, tier, "marathon",
                                                    seed, bench=bench))
                    for r in results:
                        r["quartile_stats"] = _quartile_stats(results)
                        r["drift"] = _drift(results)
                    runs.extend(results)
                continue
            for tier in tiers:
                for category, jobs in suites.items():
                    for job in jobs:
                        seed += 1
                        runs.append(_run_arm_job(policy, job, tier, mode, seed))
    return {"runs": runs, "summary": summarize(runs)}


def summarize(runs: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for r in runs:
        key = (r["policy"], r["mode"], str(r["tier"]), r["category"])
        groups.setdefault(key, []).append(r)
    lines = []
    for (policy, mode, tier, category), rs in sorted(groups.items()):
        passed = sum(1 for r in rs if r["passed"])
        lines.append({
            "policy": policy, "mode": mode, "tier": tier, "category": category,
            "jobs": len(rs), "passed": passed,
            "pass_rate": round(passed / len(rs), 2) if rs else 0.0,
            "avg_time_s": round(sum(r["metrics"]["time_s"] for r in rs) / len(rs), 1),
            "avg_actions": round(sum(r["metrics"]["actions"] for r in rs) / len(rs), 1),
            "avg_tool_changes": round(sum(r["metrics"]["tool_changes"] for r in rs) / len(rs), 1),
            "avg_sd_overhead": round(sum(r["metrics"]["screwdriver_overhead_calls"]
                                         for r in rs) / len(rs), 1),
            "avg_errors": round(sum(r["metrics"]["errors"] for r in rs) / len(rs), 1),
            "avg_damage": round(sum(r["metrics"]["damage_events"] for r in rs) / len(rs), 1),
        })
    return lines
