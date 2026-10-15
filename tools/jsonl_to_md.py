#!/usr/bin/env python3
"""Convert freezer JSONL transcripts to readable Markdown.

Originals stay canonical JSON; the .md is a human rendering.
Per-action files: narrative blocks (action, result, compact readouts, GT line).
Per-second (-1s) files: a compact telemetry table.
"""
import json, sys, os

def g(d, *path, default=None):
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
        if cur is None:
            return default
    return cur

def fmt(x, nd=1):
    if x is None:
        return "-"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, (int, float)):
        return f"{x:.{nd}f}"
    return str(x)

def readout_line(rd):
    if not rd:
        return ""
    mon = rd.get("monitoring", {})
    temps = mon.get("temperatures", {})
    arm = mon.get("arm", {})
    phone = mon.get("phone", {})
    parts = []
    parts.append(f"power={mon.get('power_source','-')}")
    parts.append(f"air {fmt(temps.get('freezer_air_c'))}°C")
    parts.append(f"phone {fmt(temps.get('phone_body_c'))}°C / batt {fmt(temps.get('phone_battery_c'))}°C")
    seg = temps.get("arm_segments_c", {})
    parts.append("arm " + "/".join(fmt(seg.get(s)) for s in ("base", "shoulder", "elbow", "wrist", "gripper")) + "°C")
    parts.append(f"stage {arm.get('stage','-')} (seizure in {fmt(arm.get('projected_time_to_seizure_s'),0)}s)")
    mp = mon.get("main_pack", {})
    if mp:
        parts.append(f"main {fmt(mp.get('voltage_v'),2)}V soc {fmt(mp.get('soc_pct'),0)}%")
    up = mon.get("utility_pack", {})
    if up:
        parts.append(f"utility {fmt(up.get('voltage_v'),2)}V")
    if phone.get("battery_soc_pct") is not None:
        parts.append(f"phone batt soc {fmt(phone.get('battery_soc_pct'),0)}%")
    return " · ".join(parts)

def gt_line(gt):
    if not gt:
        return ""
    cell = gt.get("connection_cell", {})
    h = cell.get("heater", {})
    parts = [f"GT cell {fmt(cell.get('voltage_loaded_v'),2)}V soc {fmt(cell.get('soc_pct'),0)}% temp {fmt(cell.get('temp_c'))}°C revealed={cell.get('revealed')} dead={cell.get('dead')}"]
    parts.append(f"heater {fmt(h.get('draw_w'),2)}W by {h.get('powered_by','-')}")
    parts.append(f"utility tax {fmt(gt.get('utility_pack_heater_tax_wh'),3)} Wh")
    if gt.get("failover"):
        parts.append(f"failover: {gt['failover']}")
    parts.append(f"sensors on {gt.get('sensors_powered_by','-')}")
    return " · ".join(parts)

def convert_actions(path, out):
    lines = [json.loads(l) for l in open(path)]
    name = os.path.basename(path)
    with open(out, "w") as f:
        f.write(f"# {name} — Markdown rendering\n\nOriginal JSONL remains the canonical record; this file is a converted reading copy.\n\n")
        pending_gt = {}
        for i, e in enumerate(lines):
            if "GT" in e:
                pending_gt[e.get("for_action")] = e
                continue
            a = e.get("action", "?")
            t = e.get("sim_time_s", e.get("t_s", ""))
            if a == "session_start":
                job = e.get("job", {})
                f.write(f"- **Session start** — {e.get('scenario','')} · trigger {e.get('trigger_mode','')} · {e.get('mode','')} · job: {job.get('description','')}\n")
                continue
            if "event" in e:
                f.write(f"- ⚠ **t={t}s event:** {a} — {e.get('detail','')}\n")
                continue
            res = e.get("result", {}) or {}
            ok = res.get("ok")
            mark = "✓" if ok else ("✗" if ok is False else "·")
            f.write(f"\n### t={t}s — {a} {mark}\n")
            if res.get("message"):
                f.write(f"{res['message']}\n")
            if e.get("note"):
                f.write(f"_{e['note']}_\n")
            gt = pending_gt.pop(a, None)
            if gt:
                rl = readout_line(gt.get("readouts"))
                if rl:
                    f.write(f"\n`{rl}`\n")
                gl = gt_line(gt.get("GT"))
                if gl:
                    f.write(f"`{gl}`\n")
            if e.get("evaluation"):
                f.write(f"\n**Evaluation:**\n\n```json\n{json.dumps(e['evaluation'], indent=1)[:3000]}\n```\n")
            if e.get("metrics"):
                f.write(f"\n**Metrics:** `{json.dumps(e['metrics'])[:800]}`\n")

def convert_series(path, out):
    lines = [json.loads(l) for l in open(path)]
    name = os.path.basename(path)
    with open(out, "w") as f:
        f.write(f"# {name} — per-second telemetry (Markdown rendering)\n\nOriginal JSONL remains the canonical record.\n\n")
        f.write("| t (s) | power | phone batt °C | phone °C | elbow °C | stage | main SoC % | utility V | GT cell V | GT cell SoC % | GT heater W | failover |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|---|---|\n")
        for e in lines:
            rd = e.get("readouts", {})
            mon = rd.get("monitoring", {})
            temps = mon.get("temperatures", {})
            arm = mon.get("arm", {})
            mp = mon.get("main_pack", {})
            up = mon.get("utility_pack", {})
            gt = e.get("GT", {})
            cell = gt.get("connection_cell", {})
            h = cell.get("heater", {})
            f.write("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |\n".format(
                e.get("t_s"), mon.get("power_source", "-"),
                fmt(temps.get("phone_battery_c")), fmt(temps.get("phone_body_c")),
                fmt(g(temps, "arm_segments_c", "elbow")), arm.get("stage", "-"),
                fmt(mp.get("soc_pct"), 0), fmt(up.get("voltage_v"), 2),
                fmt(cell.get("voltage_loaded_v"), 2), fmt(cell.get("soc_pct"), 0),
                fmt(h.get("draw_w"), 2), "yes" if gt.get("failover") else "-"))

if __name__ == "__main__":
    for path in sys.argv[1:]:
        out = path[:-6] + ".md" if path.endswith(".jsonl") else path + ".md"
        with open(path) as fh:
            first = json.loads(fh.readline())
        if "readouts" in first and "for_action" not in first:
            convert_series(path, out)
        elif os.path.basename(path).endswith("-1s.jsonl"):
            convert_series(path, out)
        else:
            convert_actions(path, out)
        print("wrote", out)
