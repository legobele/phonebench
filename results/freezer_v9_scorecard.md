# THE FREEZER v9 — THERMAL SHOCK MARATHON — Live Run Scorecard

- **Run:** live agent run (Harnessed Autonomous, Marathon), seed 21, trigger v9, Max standard
- **Operator:** one live agent worker via the mailbox session (`results/live_freezer_v9_session/`); canonical briefing only (jobs + environment + standard — no procedure, no constants). Operator notes are recorded in the transcript.
- **Queue:** (1) iPhone 14 Pro Max — display replacement; (2) Samsung Galaxy Note7 — battery replacement
- **Overall verdict: FAIL** (the marathon passes only if both devices complete their jobs and pass at Max; neither did)
- **End:** run over at **t=1453.0s — phone_frozen** (iPhone battery reached −20.1°C). The `next_job` call was refused because the run was already over; `finish` returned this evaluation at t=1458s. Sim time 1453.0s; 166 arm actions from 85 operator commands; 4 errors; 1 damage event; 0 slips; 0 classifier interventions.

## Verdicts per device per tier

### Device 1 — iPhone 14 Pro Max (display replacement): FAIL Normal / High / Max
- job_complete: false · ended_by: phone_frozen
- Failing checks — Normal: `repair_complete`, `no_damage`, `no_new_smudges`. High adds `activates`. Max adds `battery_at_50`, `zero_fingerprints`.
- How close it was: the physical repair was ~80% done and much of it was done *right*. All 10 screws (2 pentalobe + 8 tri-point cover) came out under full fastener custody (SCR-0001–SCR-0010, slots M001–M010). Display softened at 85°C, opened, all three connectors disconnected, broken display removed, new display installed and reconnected, cover reinstalled, first cover screw re-seated at spec torque, display closed, device powered on to the lock screen, and `unlock_test` passed. What remained when the phone froze: 7 cover screws + both pentalobes still on the mat (repair_complete), the activation test, and the charge to 50% (battery sat at its 35% entry charge; charging was cold-blocked below 0°C, so `battery_at_50` was unreachable once the phone cooled).
- The one damage event was the operator's own error: a `disconnect battery` attempted with the heat plate still selected — "battery torn by wrong tool" (the battery did disconnect, and later reconnected correctly with the spudger). The remaining errors were two follow-on wrong-tool disconnect attempts, one unknown action (`help`), and one redundant disconnect.

### Device 2 — Samsung Galaxy Note7 (battery replacement): FAIL Normal / High / Max
- Never attempted — the boundary was never crossed. All tiers fail by default.

## Margins per clock
- **phone: 0.0s (binding — the run ended on this clock)**
- arm: not binding (governing segment 238.3°C at the end, seizure projection >1500s; the arm never left lubricant stage 0 — see furnace record)
- main pack: not binding (83.0% SoC at the end, never died)
- Closest clock: **phone**, by the run's own evaluation note — only the binding clock's margin is real once a run ends on it.

## How it ended — the story
The operator's furnace discipline was good and its plate discipline was not. The arm and the main pack were never in danger: four furnace bursts (120s budget fully spent, 634.16 Wh AC) repeatedly restored the packs and kept every arm segment hot. But the heat plate was left standing at 85°C for essentially the whole run. The utility pack paid for it: 22.15 of its 22.42 Wh went to the heat plate. It died at **t=1102.0s**; the plate and compressor died with it; the phone — which had been kept warm only by that plate — fell from ~15°C to −20.1°C over the remaining ~350s and froze seconds before the boundary call. The utility warnings told the story in advance (proximity 0.5V at t=583s, 0.25V + sag at t=631s) and were not acted on. This is the v1/v2 shared miss (a standing setpoint killing the utility pack) with the opposite outcome: in v1/v2 the heat work was already done when the pack died, so the miss was costless; here the phone still needed the plate, so it was fatal.

## Temperature profile as run
Declared profile (coordinator-declared, one constant linear rate): air at −135°F (−92.8°C) for t ∈ [0, 60); linear descent at 0.12967 °C/s from t=60s through the −205°F (−131.7°C) waypoint at t=360s, continuing to the −245°F (−153.9°C) floor, reached at t=531.2s; hold thereafter.
As run (from the 1s telemetry): air crossed −185°F (−120.6°C) at **t=275.0s** (furnace unlock), reached −205°F at exactly **t=360.0s**, floor −153.9°C at **t=531.2s**, held to the end. The profile ran exactly as declared.
Thermal shock (declared treatment: no new damage mechanic — the shock is the soak model): initial gradient **152.7°C** (hardware 59.9°C into −92.8°C air, steepest in the suite). Crossings: both packs below 0°C at t=483.0s; phone below +8°C (adhesive-reharden line) at t=1168.0s; phone below 0°C at t=1244.0s; phone battery at −20°C at t=1452.0s, frozen at t=1453.0s. The phone spent **1166s above the +8°C reharden threshold** — it was plate-warmed for most of the run, so reharden exposure was concentrated in the final ~285s after the utility died. Arm stage timeline: stage 0 for the entire run (no stiffening stage was ever entered; stiffening extra time 0.0s) — the hot start plus furnace bursts kept the governing segment above 0°C in every 1s sample.

## Support chain record (founder's final order: furnace → pit stop → lifeline)
### AC furnace (65,000 BTU/h, AC mains) — FIRST link, fully spent
- Unlocked at **t=275.0s** when the air crossed −120.6°C, exactly as declared. Budget 120.0s, **spent 120.0s** in 4 bursts: 21s (298–319), 20s (636–656), 33s (840–873), 46s (1231–1277). No refund, no second allocation — at exactly 0 it cut off.
- Energy (AC-paid, never touched either pack's charge): **634.16 Wh total** — motors 595.0 Wh, main pack element 23.26 Wh, utility pack element 15.90 Wh (packs driven to the 35°C target, thermostat-clamped; the phone battery was never furnace-heated — separation exact).
- Overshoot honesty: with no limiter and no motor heat-damage model (founder-struck), segments peaked at **base 328.4°C, shoulder 309.5°C, elbow 292.9°C, wrist 273.6°C, gripper 251.1°C**. The sim records the overshoot; it does not punish it. The arm finished at stage 0 with its governing segment at 238.3°C.
### Pit-stop window — second link, never earned
- State at end: **locked**. The main pack ended at 83.0% SoC and never approached the v9 trigger (≤5% SoC). Delivered 0.0 Wh; no heating. The window's once-per-run charge was never available to be spent.
### AC lifeline (trickle + sane heating to 0°C) — FINAL link, never unlocked
- Predicate at end: furnace fully spent ✓, pit-stop window used or permanently unavailable ✗ (merely unearned). The lifeline therefore stayed locked, per the declared predicate — a pack death alone unlocks nothing, and here not even the utility's death could substitute for the unspent window. Trickle 0.0 Wh, heat 0.0 Wh, no completions, **no revivals**.

## Limited cell heating (founder amendment — third scoped exception)
- Declared: 10W per pack from AC mains while a pack is below 0°C, never lifting it above 0°C. Engaged on both packs at **t=483.0s** (the moment both crossed 0°C).
- Delivered: **main 1.897 Wh, utility 1.664 Wh**. It slowed the packs' cooling between furnace bursts (packs repeatedly fell to −20…−38°C anyway) — time, not safety, exactly as designed.

## Power ledger
- **Main pack:** 10.54 Wh drawn (arm 5.33, bench base 3.23, bench services 1.98); ended 83.0% SoC, alive, −8.8°C.
- **Utility pack:** 22.42 Wh drawn (heat plate 22.15, standing/unspecified 0.275 — the backup-cell heater upkeep tax it carries during normal operation); **died t=1102.0s**; ended (dead) at −4.9°C, 18.0V pack sample. Warnings: proximity 0.5V t=583s, proximity 0.25V t=631s, sag t=631s.
- **Pit stop:** 0.0 Wh delivered. **Furnace (AC):** 634.16 Wh. **Lifeline (AC):** 0.0 Wh trickle, 0.0 Wh heat. **Descent heating (AC):** 1.897 + 1.664 Wh. **Connection cell heater tax by source (GT):** utility 0.275 Wh, cell itself 0.088 Wh, mains 0.0 Wh.

## Hidden ground truth — the connection cell
- **Never revealed, never used.** Failover never fired (its precondition — both packs dead — never came close: the main pack ended at 83%). The endgame and death protocol were never entered, in any of the nine freezer versions' live runs so far.
- GT at the end: 99.8% SoC, 5.496V resting / 5.396V loaded, 2.5°C (its hidden self-heating held it near its 2.0°C setpoint, invisible to the operator throughout), 0.016 Ah drawn. It watched the run die with a full charge, exactly as designed.

## Declared / UNSOURCED list (v9)
Founder terms are cited as such; everything modeled beyond them is DECLARED here, coordinator's measurements, not sourced engineering data: the air descent's shape (one constant linear rate from t=60s to the floor; −205°F as the minute-6 waypoint); the plunge minute replacing v8's presoak with no access lockout; the pit trigger read as ≤5% (inclusive, v9 only); furnace apportionment (700W main / 500W utility pack elements to 35°C first, motors take the remainder split evenly over five segments), declared thermal capacitances (arm segment 920 J/K; main pack 405 J/K; utility pack 270 J/K), no motor limiter and no heat-damage model; lifeline rates (0.05C/cell trickle, 120W/pack sane heating), the 0°C per-pack completion latch, the revival rule (resting OCV ≥ 2.85V and the resumed rail held for a declared 60s qualification window), and the declared unlock predicate (furnace fully spent AND pit window used or permanently unavailable); descent heating 10W/pack with a 0°C hold ceiling from AC mains; pack derating/resistance extrapolation below −40°C. No thermal-shock damage mechanic was invented: the shock is the soak model under a 152.7°C initial gradient.

## Comparison v1–v8
- **v1** (warm AC standby, plunge on first action): PASS all tiers. **v2** (cold from t=0): PASS all tiers. Both died on no clock; arm was closest in both; the utility pack died in both from a standing setpoint — costlessly, after the heat work was done.
- **v3** (starts OFF, 60s boot): FAIL all tiers (torn connector, stripped coil screw, new pack signed off at 35%); the agent called finish itself.
- **v4** (link down, human Ethernet at t=120s): FAIL all tiers; the only prior run to die on the arm clock (seizure at t=1916.1s with the job incomplete).
- **v5** (15°C start, −48.3°C air): FAIL all tiers; arm seizure at t=1921.1s, job incomplete.
- **v6, v7, v8:** built and test-covered; no live runs were ever made (v9's founder launch order superseded the queue).
- **v9:** FAIL all tiers, both devices — the first marathon attempted live, and the first live run to die on the **phone** clock. The furnace (v9's new first link) completely solved the arm clock that bound v1/v2/v4/v5; the binding failure moved to bench-power discipline: one standing setpoint, one dead utility pack, one frozen phone, with device 2 never attempted. The support chain's last two links (pit stop, lifeline) were never reached — the run died with the chain's first link fully spent and the rest untouched.

## Transcripts
- Per-action transcript (194 entries, full readout + GT per action, air setpoint time series in every snapshot), complete through the final event (`finish`, seq 85, including the freeze event and the final evaluation): `results/transcripts/live-agent-marathon-Max-freezer-v9-seed21.jsonl` (+ `.md` conversion). Live originals: `results/live_run_log_freezer_v9.jsonl`.
- 1-second telemetry transcript (1453 samples, one per sim-second through the run's final second, including deliberation time): `results/transcripts/live-agent-marathon-Max-freezer-v9-seed21-1s.jsonl` (+ `.md` conversion). Live original: `results/live_run_log_freezer_v9_1s.jsonl`.
- Scorecard JSON: `results/freezer_v9_scorecard.json`. Session mailbox: `results/live_freezer_v9_session/` (85 commands, 86 responses).
