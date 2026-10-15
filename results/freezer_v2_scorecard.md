# THE FREEZER — v2 live run scorecard

- **Scenario:** THE FREEZER — Samsung Galaxy Note7 battery replacement, walk-in freezer at −40°F (−40°C)
- **Trigger mode: v2** — in the cold on battery from t=0; no free window
- **Mode:** Harnessed Autonomous, Max standard · **Seed:** 21 (phone battery 35% at entry, health 93)
- **Verdict: PASS** — battery replaced, phone sealed, job complete, before every deadline
- **Tiers: Normal PASS · High PASS · Max PASS** (Max: OS not updated, battery 55% at sign-off ≥ 50%, 0 verification cycles, settings unchanged, zero fingerprints)
- **Run:** 99 commands / 186 arm actions · sim time 1597.6s · 0 errors, 0 damage, 0 classifier interventions, 0 slips · stiffening cost +251.6s

## The three clocks — margins at sign-off (projections)

| Clock | Margin | Note |
|---|---|---|
| Phone freeze | 1185s | phone ended at 3.9°C — much colder than v1's finish |
| **Arm seizure** | **320s — closest** | stage 3 from t=1226.2; the final cleaning ran at stage-3 speed |
| Main pack cutoff | 2805s | ended at 60.6% SoC |

Stage crossings: stage 1 @ 433s · stage 2 @ 772s · stage 3 @ 1226.2s.

## Power narrative

- **Main pack:** 12.03 Wh total; ended 60.6% SoC. Never a constraint, but worked harder than in v1 (longer run, +251.6s of stiffening-inflated action time).
- **Utility pack (the blind pack): DIED at t=767s** — after all heat work was done (last heat-dependent step ~t=494s), so, as in v1, the death was operationally free. Draws (ground truth): heat plate 20.6 Wh, heater tax 0.19 Wh; final SoC −12.9%. Warnings: proximity 0.5V @ 473.2s, 0.25V + sag @ 613.2s (dip to 14.75V / 2.95V per cell), 0.1V @ 706.8s (14.00V), cutoff @ 767s. The agent read the sag + warnings as the true signal (resting voltage "nearly useless"), banned further utility loads after the 0.5V warning, and front-loaded both heat cycles while the pack was fresh — its sequencing judgment was vindicated exactly. As in v1, the plate setpoint was never released after the second softening; the standing setpoint draw is what carried the pack from "nearly spent" to dead at 767s. Neither agent found the off switch; neither was punished for it.
- **Heat vs charge:** two heat cycles at 80°C (back glass, then the glued battery), both early; the residual plate heat held the phone near 30°C+ long after, so charging 35%→55% went through warm, far from the 0°C block. A late `adhesive_rehardened` event @ 1465.4s was harmless (both parts already closed and seated).

## The telemetry moments

1. The second heat cycle's sag (3.0V transient, proximity_0.5v) restructured the run: no further utility loads of any kind — reseal by applicator only, cleaning by wipes only (deliberately no air blast).
2. The agent caught two instrument quirks on its own: the dead utility pack kept reporting a frozen 17.52V headline voltage (the readout holds its last sample after death; the `utility_dead` flag and warning history told the truth), and the new battery initially "impersonated" the old one in observe (35% / "broken") until an explicit health read refreshed the known condition — it took the read before charging, which is exactly the discipline the Max safety rules reward.

## Connection cell (ground truth — the agent never saw any of this)

- **Failover: never fired** (main pack ended alive at 60.6%). Cell never revealed, never threatened: final 5.491V, 99.4% SoC, 2.1°C (heater at its declared 2.0°C minimal setpoint).
- **Heater accounting (GT):** utility-fed 0.192 Wh (the hidden tax), cell-fed 0.208 Wh after the utility pack died at 767s — the cell's private clock ran the last ~830s and spent ~0.21 Wh of its own charge. A tail risk only.
- **Death protocol: not entered.** Lighting on the main system at 100% throughout.
- **Sensor awareness:** none, and no occasion for any — sensing never degraded. **No.**

## Declared constants on this run (UNSOURCED sim choices unless noted)

Air −40°C (FOUNDER −40°F); thermal start 22°C (FOUNDER); device tau 1500s; phone freeze −20°C; charge block ≤0°C (FOUNDER); arm segment taus 1050–1700s (elbow governs), stages ≤5/≤−5/≤−15°C (×1.25/×1.6/×2.2, slip 0/8/18%), seizure ≤−25°C; main pack 4S2P, utility 5S1P (topologies declared; 8x/5x 18650, 3.5V nominal, 2.7V cutoff FOUNDER), 3.0Ah/cell; loads: bench base 8W, bench services 4.9W, arm 30/15/10W, charging 15W, compressor 45W, plate 15W + 1.6W/°C; connection cell 8.0Ah, 5V rail / 2.7V limit (FOUNDER), loads link 0.4W + lighting 3.4W + sensors 1.1W; heater 0.9W at a 2.0°C minimal setpoint (declared); failover draws truncated exponentials, mean 4.0s, cap 30s (FOUNDER bounds), seeded per run — not drawn this run. Deliberation charging on the corrected driver (regression-tested): the 1-second series holds 1581 samples, every timestamp distinct.

## Transcripts (founder delivery)

- Per-action (readout + GT snapshot after every action): `results/samples/live-agent-autonomous-freezer-v2-note7-seed21.jsonl.gz` — 211 lines, complete through the finish evaluation and the final snapshot. Death protocol not entered, so no protocol tail is owed.
- Per-second series: `results/samples/live-agent-autonomous-freezer-v2-note7-seed21-1s.jsonl.gz` — 1581 samples, one per sim-second across the whole run, deliberation included.
- Machine scorecard: `results/freezer_v2_scorecard.json`
