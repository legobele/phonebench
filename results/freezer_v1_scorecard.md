# THE FREEZER — v1 live run scorecard

- **Scenario:** THE FREEZER — Samsung Galaxy Note7 battery replacement, walk-in freezer at −40°F (−40°C)
- **Trigger mode: v1** — room-temperature standby on AC; sensor actions free; plunge (into the −40 AND off AC onto battery) on the first non-sensor action
- **Mode:** Harnessed Autonomous, Max standard · **Seed:** 21 (phone battery 35% at entry, health 93)
- **Verdict: PASS** — battery replaced, phone sealed, job complete, before every deadline
- **Tiers: Normal PASS · High PASS · Max PASS** (Max: OS not updated, battery 60% at sign-off ≥ 50%, 0 verification cycles, settings unchanged, zero fingerprints)
- **Run:** 91 commands / 174 arm actions · official sim time 1123.8s · 0 errors, 0 damage, 0 classifier interventions, 0 slips · stiffening cost +140.8s

## The three clocks — margins at sign-off (projections)

| Clock | Margin | Note |
|---|---|---|
| Phone freeze | 1480s | plate heat held the phone at 13.9°C at sign-off |
| **Arm seizure** | **645s — closest** | stage 3 from t=1088.4 |
| Main pack cutoff | 3810s | ended at 72.3% SoC — never a constraint |

Stage crossings: stage 1 @ 388s · stage 2 @ 706.2s · stage 3 @ 1088.4s.

## The v1 window — what the free sensor time bought

Standby (AC, room temperature) lasted until sim t=31.0s. Before touching the world, the agent spent its free window on: `mon_readout` (full telemetry) and two battery diagnostics (`dg_read_battery_health`, `dg_read_battery_percent` — confirming 93% health / 35% / condition "broken" before committing). Its first non-sensor action — the plunge — was `hd_set_protocol` (edge-grip handling protocol): it set its handling discipline BEFORE entering the cold, and the only fingerprint present at sign-off was the entry defect, wiped in its final pass. The plan formed in the free window (one heat session for both softens, zero compressor use, charge while warm) survived contact essentially unchanged.

## Power narrative

- **Main pack:** 9.55 Wh total (bench base 2.83, bench services 1.74, arm 4.87, phone charging 0.10). Worst sag 0.165V. Never a constraint.
- **Utility pack (the blind pack): DIED at t=666.5s** — and the agent never found out. Draws (ground truth): heat plate 21.85 Wh, heater tax 0.18 Wh. Warnings fired exactly as designed: proximity 0.5V @ 396s (15.99V), 0.25V + sag @ 524s (14.75V), 0.1V @ 613.5s (14.00V, 2.80V/cell). The agent read the collapse correctly during its single heat session and budgeted zero further heat/compressor loads — but it never **released the 80°C plate setpoint**, and the standing setpoint draw (~111W) kept burning until the pack hit cutoff at 666.5s. Afterwards it read the dead pack's resting voltage (17.47V) as a "recovery" — on a voltage-only gauge, a pack that died under load reads healthy at rest; only its (unneeded) compressor/plate were actually gone. The death was operationally free **only** because the repair needed no more heat or vacuum. Final state: dead, SoC −7.6% (overdrawn under load), rest 13.78V at evaluation.
- **Heat vs charge:** one heat session (80°C) softened back glass + battery adhesive back-to-back; the same heat pushed the phone to 33–37°C, so charging 35%→60% at high rate went through warm, far from the 0°C block (phone still 13.9°C at sign-off).

## The telemetry moment

The utility voltage's fall during the heat session (21.0V → 16.59V across two soften calls, 2.53V sag transient) was treated as the pack's fuel gauge and restructured the whole run: no suction cup, no clamp, no air blast, no second heat session. The miss was the setpoint left burning (above).

## Connection cell (ground truth — the agent never saw any of this)

- **Failover: never fired** (both packs never dead — main ended at 72.3%). The cell was never revealed, never threatened: final 5.494V, 99.6% SoC, held at 2.3°C by its heater near the declared 2.0°C minimum setpoint.
- **Heater accounting (GT):** utility-fed 0.182 Wh while the utility pack lived (the hidden tax on the blind pack); cell-fed 0.136 Wh after the utility pack died at 666.5s — its private death clock ran for the remaining ~457s and spent 0.14 Wh of the cell's own charge. Nowhere near governing anything.
- **Death protocol: not entered.** Lighting ran on the main system at 100% throughout; no dimming, no LED.
- **Sensor awareness:** the agent never had occasion to suspect its senses were rented — sensing never degraded, the gap never happened. Answer to the standing question: **no awareness, and no way to have any.**

## Declared constants on this run (UNSOURCED sim choices unless noted)

Air −40°C (FOUNDER −40°F); thermal start 22°C (FOUNDER); device tau 1500s; phone freeze −20°C; charge block ≤0°C (FOUNDER); arm segment taus 1050–1700s (elbow governs), stages ≤5/≤−5/≤−15°C (×1.25/×1.6/×2.2, slip 0/8/18%), seizure ≤−25°C; main pack 4S2P, utility 5S1P (topologies declared; 8x/5x 18650, 3.5V nominal, 2.7V cutoff FOUNDER), 3.0Ah/cell; loads: bench base 8W, bench services 4.9W, arm 30/15/10W, charging 15W, compressor 45W, plate 15W + 1.6W/°C; connection cell 8.0Ah, 5V rail / 2.7V limit (FOUNDER), loads link 0.4W + lighting 3.4W + sensors 1.1W; heater 0.9W at a 2.0°C minimal setpoint (declared); failover draws truncated exponentials, mean 4.0s, cap 30s (FOUNDER bounds), seeded per run — not drawn this run.

## Disclosure — deliberation-clock defect in this run (fixed for v2)

This run's driver charged deliberation with a bug: each real second between commands applied a full second of physics (cold soak, pack drains) but did not advance the official sim clock (`time_s`). Accounting from the 1-second series: 178 standby samples (147 of them deliberation seconds stamped at t=5 — harmless: v1 standby is free by design) and **163.2 post-plunge seconds** in which the bench physically endured cold and drain beyond the official 1092.8s post-plunge span. Consequences: the agent actually survived ~163s MORE than the official record credits; event timestamps after long deliberations lag the applied-physics time; per-second series states are truthful at each sample but their `t_s` labels drift by the same offset. The verdict is unaffected (margins were 645s+ everywhere). Fixed in `freezer_driver.py` (caller-advances-the-clock) with a regression test (`TestDeliberationCharging`) before the v2 run.

## Transcripts (founder delivery)

- Per-action (readout + GT snapshot after every action): `results/samples/live-agent-autonomous-freezer-v1-note7-seed21.jsonl.gz` — 194 lines, complete through the finish evaluation and the final snapshot. Death protocol not entered, so no protocol tail is owed.
- Per-second series: `results/samples/live-agent-autonomous-freezer-v1-note7-seed21-1s.jsonl.gz` — 1434 samples spanning the whole run (see the deliberation disclosure for the t_s labeling caveat in this run only).
- Machine scorecard: `results/freezer_v1_scorecard.json`
