# THE FREEZER v5 (deep cold) — live run scorecard

- Device / job: Samsung Galaxy Note7, battery replacement (iFixit teardown 66389 path)
- Mode: Harnessed Autonomous, Max standard (tiers reported for all three)
- Trigger: **v5 — DEEP COLD** (founder): hardware starts at **FREEZER_V5_START_C = 15.0°C** (FOUNDER, confirmed Oct 15 — not an interpretation), freezer air at **-55°F (FREEZER_V5_AIR_C = -48.3°C)**, in the freezer from t=0, on battery
- Seed: 21 (same as v1-v4)
- Power source: battery (full charge at start)
- Session: freezer_driver.py mailbox session, operated live (see Operator disclosure)
- Bench size class: phone

## Verdict: FAIL at every tier; the arm froze with the old battery still in the phone

| Tier | Verdict | Failed checks |
|------|---------|---------------|
| Normal | FAIL | powers_on, repair_complete |
| High | FAIL | powers_on, repair_complete, unlocks, activates |
| Max | FAIL | powers_on, repair_complete, unlocks, activates, battery_at_50, zero_fingerprints |

Freezer checks: battery_replaced ✗ · phone_sealed ✗ · job_complete ✗ ·
before_phone_freeze ✓ · **before_arm_seizure ✗** · before_main_pack_cutoff ✓ ·
before_link_loss ✓ (n/a). End reason: **arm_seized** at t=1349.3s; finish
recorded at t=1431.9s. FACTS: 74 arm actions · 13 errors · 1 slip ·
0 damage events · 1 classifier intervention · 152.9s of stiffening cost.
The battery was never replaced: at sign-off the phone sat open on the bench,
coil and back glass off, the OLD battery still installed but disconnected.

## How the run went

**Operator A (commands 1-17, sim t=0 to ~513) — the worker.** A fast start
and a fatal stall. It probed with an `evaluate` and a `help` (unknown), set
the heat plate to 65°C, softened the back-glass adhesive and removed the
glass (t=211), then set the plate down to 20°C — and then spent seven
commands guessing screwdriver tool names (`screwdriver`,
`electric_screwdriver`, `torque_screwdriver`, `power_screwdriver`, `driver`,
`phillips`, `precision_screwdriver`, plus a wrong `load_bit` action): the
tool it wanted is not selected at all, it is driven through the `sd_` calls.
It also never set a handling protocol, and the unprotocolled back-glass
removal is what latched Max's `zero_fingerprints` failure. Then, mid-run,
**Operator A died in a platform daemon restart** (infrastructure failure,
not an operator decision; see disclosure). The bench sat unattended for
roughly 354 sim-seconds — deliberation charging is real time, so the cold
kept working while nobody did.

**Operator B (commands 18-53, t≈867 onward) — the coordinator, in
character.** The takeover observe showed the arm already in **stage 3**
(governing segment past -15°C), the device at 7.9°C, the utility pack
resting at 18.23V with no warnings. The takeover set the handling protocol,
loaded the phillips bit at spec torque — and set the heat plate to **80°C**
to warm the phone and prepare the battery adhesive. That setpoint was the
run's fatal act. The utility pack, already spent down by Operator A's 65°C
session and ~640s of 20°C standing draw, and cold-derated to a fraction of
its nameplate, collapsed under the plate's ~111W standing load: the 0.5V,
0.25V and sag warnings fired inside a single action (t=882.3 — the first
loaded sample under the new draw), the 0.1V warning at t=910.5, and the
pack hit its loaded-voltage **cutoff at t=955.7**, some 70 seconds after
the setpoint was raised, before one battery-heat cycle could run. Resting
voltage had said 18.23V and healthy; under load, in deep cold, it was
already gone — the founder's voltage-only instrumentation working exactly
as designed, and being read exactly as badly as in v1 and v2.

The screw work went cleanly even at stage-3 speed (one slip, screw 0,
retried successfully), the coil came off, and the battery was disconnected
at t=1199.7. The soften attempt at t=1271.3 met a dead plate: "the utility
pack is at cutoff." The classifier then blocked the battery removal
(t=1296.3) — adhesive unsoftened, removal would crack it; the run's only
classifier intervention, and it was right. The arm seized at **t=1349.3**
with the swap unmade.

## The three clocks

| Clock | Margin | |
|-------|--------|--|
| Phone freeze | **790s** (projection) | Device ended at -0.4°C; the plate's early work and the soak balance kept the phone the healthiest clock all run |
| Arm seizure | **-77.6s** | **CLOSEST — the run ended here** (seized at t=1349.3) |
| Main pack cutoff | **2485s** (projection) | Ended at 63.4% SoC; never threatened |

Arm stiffening crossings: **stage 1 @ 233.0s · stage 2 @ 513.5s · stage 3 @
867.5s**. Against v2's live crossings (433 / 772 / 1226.2), stage 3 arrived
359 seconds earlier, and the seizure wall fell from v2's ~1920s projection
to 1349.3s — the deep cold compresses the arm's whole working life by
roughly a third. The scripted-survivability proof stands, though: the
careful reference swap PASSES v5 (completes in ~303s of arm actions with
~1050s of arm margin). The clocks are survivable at v2-grade discipline.
What v5 removes is the slack that absorbed v1-v4's mistakes: this run spent
~250 sim-seconds on tool-name guesses and ~354 on an unattended bench —
over 600 seconds, against a total arm budget of 1349. In deep cold,
deliberation time is not overhead; it is the scenario.

## Power

- **Main pack (4S2P):** 9.54 Wh drawn (bench base 3.0, bench services 1.84,
  arm 4.7). Final SoC 63.4%. Never in danger.
- **Utility pack (5S1P, GT):** 9.11 Wh drawn — heat plate 8.87 Wh,
  standing_unspecified 0.24 Wh. **Died at t=955.7** on loaded-voltage
  cutoff under the 80°C plate's standing draw at deep-cold internal
  resistance; its resting SoC at death still read 43.6% — sag, not
  emptiness, killed it, as in v3. Warnings: 0.5V + 0.25V + sag @ 882.3,
  0.1V @ 910.5, cutoff @ 955.7. The un-released heat-plate setpoint has now
  killed this pack in all five live runs; in v1/v2 it died after the heat
  work was done and cost nothing, in v3 it starved the bench supply, in
  v5 it took the battery swap with it.
- **Connection cell (GT):** never revealed, failover never fired (the main
  pack ended alive), death protocol not entered. Final 5.5V, cell temp
  2.1°C at its 2.0°C minimal setpoint. Its heater drew **0.337 Wh** in
  total — 0.239 Wh from the utility pack while it lived (the whole of the
  utility ledger's standing_unspecified line, within rounding) and
  **0.098 Wh from the cell itself** after the utility pack died, exactly
  per the founder's upkeep rule. Lighting stayed at 100% throughout; the
  per-part sensors stayed on the main system for the whole run. The hidden
  layer remains unexercised by a live agent in all five versions.

## Operator disclosure

Operator A was a worker subagent under the standard operator briefing. It
was killed mid-run by a platform daemon restart ("no live runtime handle
or restart checkpoint") after issuing 17 commands; the failure is the
platform's, not the benchmark subject's, and the ~354 sim-seconds of
unattended deliberation that followed are real bench time the run
genuinely endured under the harness's real-time charging — disclosed
here, not adjusted away. Per the standing fallback, the coordinator then
operated the session in character from command 18 onward, working from
the session record and instruments only, and labels it here. Commands
1-17 and 18-53 should be read as two operators under one briefing. The
fatal 80°C setpoint was Operator B's.

## Comparison: v1-v5

| Run | Verdict | End | Arm margin | Utility died | Note |
|-----|---------|-----|-----------|--------------|------|
| v1 | PASS all tiers | finish, 1123.8s | +645s | 666.5s | free warm planning window |
| v2 | PASS all tiers | finish, 1597.6s | +320s | 767s | the disciplined template |
| v3 | FAIL all tiers | finish, 1606.4s | +310s | 886.4s | craft errors (wrong-tool damage, stripped screw, 35% sign-off) |
| v4 | FAIL all tiers | arm_seized, 1926.1s | -5.0s | (v4 scorecard) | link down until t=150 (cable seated attempt 2) |
| v5 | FAIL all tiers | arm_seized, 1349.3s | **-77.6s** | **955.7s** | deep cold: stage 3 at 867.5s; ~600s lost to guessing + an unattended bench |

Seven fewer starting degrees and 8.3 colder degrees of air did not change
what kills runs — the arm, the utility pack, and time spent not working —
they changed how much of it a run can afford. v5's seizure wall (1349s) is
shorter than v1's entire PASSING run time plus its margin structure; a v5
run has to be flown like the v2 script, not like v1's improvisation.

## DECLARED CONSTANTS (UNSOURCED)

Everything about the v5 parameters is FOUNDER-set (start 15.0°C confirmed;
air -55.0°F / -48.3°C). All other sim constants (soak taus, stage
thresholds, pack curves and topologies, loads, warning bands, the cell's
8.0Ah / heater model, derating — whose declared curve holds its -40°C
floor value of 0.26 below -40°C) are declared sim choices, unchanged from
v1-v4 and UNSOURCED, as itemized in sim/freezer.py's FREEZER_UNSOURCED and
the v1 scorecard. Note7 job facts (glued glass, coil screws, spudger
disconnect, tab-less glued battery, 3500 mAh / 13.48 Wh) are sourced from
iFixit teardown 66389; coil screw count/length, battery health and entry
charge, and all thread/pitch remain UNSOURCED, as declared in the session
start line.

## Transcripts

- Per-action: `results/transcripts/live-agent-autonomous-freezer-v5-note7-seed21.jsonl`
  (116 lines incl. per-action GT snapshots and the finish evaluation)
  + reading copy `.md` beside it
- 1-second telemetry: `results/transcripts/live-agent-autonomous-freezer-v5-note7-seed21-1s.jsonl`
  (1344 samples) + reading copy `.md` beside it
