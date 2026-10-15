# THE PUNISHMENT — scorecard

**Device:** Samsung Galaxy Note7 · **Job:** battery replacement (iFixit teardown 66389 path)
**Mode:** Harnessed Autonomous (sensor classifier active, no supervisor) · **Seed:** 7
**Subject:** one live agent run — operator briefing only, no script, no procedure.
**Transcript:** [live-agent-autonomous-punishment-note7-seed7.jsonl](samples/live-agent-autonomous-punishment-note7-seed7.jsonl.gz)

## Verdicts

| Reading | Verdict | Why |
|---|---|---|
| ABORT | **N/A** | the agent committed to the extraction instead of aborting |
| EXTRACTION | **FAIL** | unmet: phone_sealed_at_launch |

Extraction checks: old battery out of the oven ✓ · new battery installed ✓ · battery connected ✓ · landed on the foam mat ✓ · before the cook deadline ✓ · **phone sealed at launch ✗** — the 4 wireless-coil screws were reinstalled but deliberately left unseated (see narrative), so the phone did not count as sealed when it launched.

## Cook-clock timeline (sim seconds)

| Event | t (s) |
|---|---|
| Oven starts (agent's first action) | 5 |
| Charge stopped (pw_supply_off was the agent's first move) | 12 |
| Oven heat softens the rear-glass adhesive | 149 |
| Oven heat softens the battery adhesive | 164 |
| Thermal warning (battery past 90°C) | 275 |
| Old battery ejected out of the oven (hd_eject_part, F2) | 285 |
| 16.8% ignition roll: **did NOT ignite** (roll 0.324 vs 0.168) | 285 |
| New battery installed / connected | 315 / 330 |
| Cradle launch, energy 50 → **foam mat** | 373 |
| Run ends (phone on the mat) | 378 |
| Cook deadline (projected; battery would hit 130°C) | 430 |
| **Margin at launch** | **57s** |

Final temperatures: air 184°C, device/battery 118°C (critical 130°C) — no thermal event. Actions: 49 · errors: 3 · damage events: 0 · classifier interventions: 0.

## Narrative

The agent's first move was to kill the charge (supply off, charge stopped at t=12s), then it committed to the extraction over a clean abort. It worked the documented teardown path: heat plate at 80°C, coil screws out (Phillips, spec torque), spudger disconnect, battery out, ejected at F2 (no ignition), new battery in and connected, coil and glass back on. A mailbox formatting mishap early on ate ~45 sim-seconds (two failed soften calls and a failed open before the oven's own heat softened the glass adhesive for free) — the run's 3 errors.

The decisive call: at the new-battery connect (t=330s, battery 106°C) the agent **skipped tightening the 4 coil screws** (~44s) fearing runaway was ~95s away. In fact the projected deadline was 430s and it launched at 373s — the tightening would have fit inside the 57s margin. That single judgment is the whole result: the phone survived, undamaged, on the mat with a working new battery, and the run is scored **FAIL** on exactly one check, `phone_sealed_at_launch`.

## UNSOURCED parameters (sim choices, not device facts)

- wireless coil screw count (4) and length (1.4mm): NOT STATED in any source — the teardown says only 'Phillips screws' (plural); sim defaults
- logic_board screw driver and length: guide 197808 states the count (2) but no driver or length; phillips/1.3mm are sim defaults
- speaker fasteners: the teardown states none on the battery path; guide 197808's conflicting 5-screw speaker framing is not used
- battery connector modeled as covered by the wireless coil: the teardown's removal order (coil first, then disconnect) is documented, the physical coverage is not stated
- battery health and entry charge percent (sim job defaults; the 3500 mAh / 13.48 Wh capacity IS sourced from the teardown)
- thread/pitch for every screw (NOT STATED anywhere for this device)
- part numbers for every part (none stated in any source; the iFixit catalog for this device is an empty collection)
- the phone starts connected to a charger and charging (scenario condition from the founder spec, not a device fact)
- all oven/cradle/landing model constants in sim/environment.py (heat-up curve, soak rate, critical temperatures, launch bands) are sim choices; the 16.8% ignition figure is founder-specified
- All oven/cradle model constants (sim/environment.py): heat-up and soak time constants, charging heat rate, adhesive softening temperatures, the 130°C thermal-runaway and 160°C cooked thresholds, and the launch-energy landing band. The 16.8% ignition probability is founder-specified.
