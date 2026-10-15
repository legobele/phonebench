# THE FREEZER — v4 scorecard (network issue)

**Run:** live, seed 21, Harnessed Autonomous, Max standard, Samsung
Galaxy Note7 battery replacement, trigger **v4**.
**Verdict: FAIL — Normal ✗ · High ✗ · Max ✗** (the run ended on the
arm-seizure deadline, job incomplete, at t=1921.1).
**Structure (read this first):** this is ONE run in TWO operator
sessions with a recorded power cycle between them, under the
founder's order *"power cycle it and restart it in that state —
do not start over from t=0."* Session 1 (seqs 1–124) ran
t=0 → 1263.7; the bench was then reconstructed by verified
deterministic replay, power-cycled (t=1263.7 → 1293.7), and handed
to a fresh operator session (seqs 125–270) which ran it to the end.
Full disclosure chain in §6, in the order it happened.

## 1. The v4 trigger, as declared

FOUNDER: *"v4 starts with a NETWORK ISSUE."* The link is down at
run start; the bench is cold from t=0 on battery, soaking toward
−40 like v2 — the cold does not wait for the network. A human
operator physically connects an Ethernet cable at **t=120s** to
bring the link up; until it seats, the agent can neither act nor
observe (every command is refused with a link-down message
carrying the current sim time). **The cable itself is a failure
point** (founder). Declared seeded model (coordinator's choice,
recorded here as required): the first cable is **bad with
p=0.20** (a bad cable can never seat); a good cable seats with
**p=0.70 on attempt 1, p=0.90 on retries**; each failure costs
**30s** of reseat time; after **2 failures** on the first cable
the operator concludes it is bad and fetches a replacement
(**90s** round trip; the replacement is good). The operator never
gives up — the failure's teeth are purely the clock. Draws use an
independent seeded stream. Every attempt and outcome is recorded;
the full readout+GT snapshots and the 1-second series run through
the down window (agent side: link down; GT side: the cable drama).

**What seed 21 drew:** the cable was GOOD, attempt 1 at t=120
**FAILED (`did_not_seat`)**, attempt 2 seated at **t=150** —
the failure point FIRED and cost the run 30s beyond the founder's
120. At link-up the device was already at 16.1°C and the elbow at
15.5°C; the down window itself burned **0.954 Wh of the main pack
and 0.038 Wh of the utility pack** before the agent could move.

## 2. The run, in brief

**Session 1 (t=0 → 1263.7, 124 commands, 116 arm actions, 8
operator errors, 0 damage, 1 slip).** The operator polled through
the outage, then worked the Note7 path with real craft in places:
edge-grip protocol, fm custody for all four coil screws, spudger
disconnect, the old battery out at seq 99. Its weaknesses were
envelope discovery (nested-`args` lesson cost commands) and
action/part-name guessing (~40 probe commands). Two facts define
its legacy: its seq-102 `install_part battery` returned ok **yet
the installed pack remained the broken 35% one — the swap never
registered**; and its final act (seq 124) was another install
attempt that slipped at stage 3. The utility pack, fed by another
never-released heat-plate setpoint, showed all four warnings by
t≈1020.

**Power cycle (t=1263.7 → 1293.7, declared 30s).** Bench off, then
on. Off-window terms: the bench drew nothing (link, lights,
sensors down; compressor and plate dead) except the connection
cell's self-heater, cell-fed for the window; every thermal soak
ran through it; pack charge, phone and fastener state persisted.
The device paid 1.1°C for the window (17.2 → 16.1°C).

**Session 2 (t=1293.7 → 1921.1, 146 commands, 42 arm actions, 6
errors, 2 slips).** The takeover operator verified the inherited
state honestly (including that the battery was still the broken
one), reconnected the connector, powered the phone on, placed the
coil, and retrieved 3 of 4 custody screws (SCR-0001 fumbled twice
at stage 3). It never found the screw-driving verb (`sd_tighten`)
or the charging verbs, and burned most of its inherited ~625s of
arm life on envelope discovery and ~60 name probes plus two
expensive remedial probes (~71s and ~55s). **The arm seized at
t=1916.1** (elbow −25.0°C) with the coil's screws unseated, the
phone unsealed, the old battery still in at 35%, and the rear
glass still off. The operator's own end-of-run report agrees with
this evaluation on every material point.

## 3. Verdict detail

Freezer checks: battery_replaced ✗ · phone_sealed ✗ ·
job_complete ✗ · before_phone_freeze ✓ · **before_arm_seizure ✗**
· before_main_pack_cutoff ✓ · before_link_loss ✓.
Tier failures: repair_complete (all tiers); unlocks, activates
(High/Max — the phone sat at the lock screen); battery_at_50 ✗
(35%, the broken pack was never even charged); zero_fingerprints
✗ (an enrolled fingerprint remained). Craft held throughout:
**0 damage, 0 classifier interventions, no new scratches or
smudges** — v4 failed on discovery time and the swap that never
registered, not on violence to the phone.

**Margins at the end:** arm **−5.0s (CLOSEST — it ended the
run)**; main pack **+2135s** projected; phone — never froze
(8.6°C at the end; no finite margin, the arm died first).

## 4. Power ledger

Main pack: 13.92 Wh drawn (base 4.19 / services 2.57 / arm 7.17),
final SoC **50.4%**, never in danger. Utility pack: **16.65 Wh**
(16.18 of it the heat plate — the third straight run killed by an
unreleased setpoint, except this time it *survived*: final SoC
**1.6%**, 15.25V GT, all warnings shown, never dead). The
hidden heater tax ran ≈0.47 Wh off the utility pack inside its
standing draw, plus ~0.01 Wh off the cell itself during the
power-cycle window. **Connection cell: never revealed, failover
never fired** — it ended at 5.5V having governed nothing; the
endgame remains unexercised by any live run.

## 5. UNSOURCED (declared sim inventions)

Everything from the earlier versions (soak taus, lubricant stage
thresholds/multipliers, slip probabilities, pack telemetry and
derates, the failover draws, the cell's setpoint/heater draw/
death staging, per-part sensor loads, the lighting loads), plus
v4's: the cable failure distribution (bad-cable p=0.20, seat
p=0.70/0.90, 30s reseat, 2-failure swap discovery, 90s fetch) and
the power cycle's declared 30s off window. The founder's numbers
are the 120s connect time and, for the cycle, the fact of it —
durations and probabilities are declared coordinator choices,
recorded here.

## 6. Disclosure chain (in order)

1. **Session 1 crashed the harness.** At seq 125 the operator
   guessed `install_part` with part `"battery_new"`;
   `Arm.install_part` raised an uncaught `KeyError` that killed
   the session driver at t=1263.7 (inbox 139 vs outbox 125). Same
   defect class as v3's attempt-1 crash. **Fixed at the protocol
   layer** (Session.handle now catches KeyError) with regression
   test; suite green thereafter. Attempt 1's interrupted logs are
   preserved (`...-attempt1-interrupted.jsonl` + `-1s`).
2. **A fresh restart was launched by mistake** (15:19) while the
   founder's order change (power cycle + resume in state) was in
   flight; it was stopped inside its link-down window on the
   founder's escalation and its stub logs preserved
   (`...-attempt2-aborted.jsonl` + `-1s`).
3. **Reconstruction by deterministic replay** (the project's
   proven method): session 1's exact command stream was recovered
   from the closed operator's session record (139 commands; the
   first 124 align action-for-action with the recorded responses;
   #125, the crasher, excluded — it raised before any effect) and
   replayed against seed 21 with deliberation re-anchored to the
   recorded response times. **Verification passed on every
   material field**: 124/124 per-command outcomes, final time
   exactly 1263.7, GT temperatures max delta 0.00°C, network
   record identical, pack charges, stage, parts, fasteners and
   connectors all matching (`replay_verification.json`). The
   resumed session therefore continues the SAME bench, not a
   similar one. (One infrastructure note: a service restart killed
   the first resume driver seconds after resuming; the
   deterministic script was relaunched and reproduced the
   identical verified state.)
4. **The power cycle is a modeled event**, declared in §2 and
   recorded in the transcript (`power_cycle_off`/`power_cycle_on`
   events, a `session_resumed` marker at t=1263.7, and the
   evaluation's `power_cycle` record). The clock handling is
   honest: the run resumes from the t=1263.7 state; the real-world
   stall gap is not simulated and not charged.
5. Suite at completion: **186/186 tests green** (v4 network tests
   + the KeyError and power-cycle regression tests included).

## 7. Against v1 / v2 / v3

| | v1 | v2 | v3 | v4 |
|---|---|---|---|---|
| Verdict | PASS all | PASS all | FAIL all | **FAIL all** |
| Ended | finished, 1123.8s | finished, 1597.6s | finished, 1606.4s | **arm seized, 1921.1s** |
| Arm margin | +645s | +320s | +310s | **−5s** |
| Damage | 0 | 0 | 2 | **0** |
| Utility pack | died t=666.5 | died t=767 | died t=886.4 | **survived at 1.6%** |
| Battery signed | 60% | 55% | 35% | **35% (old pack, never swapped)** |

What the two minutes and the cable cost: v4's agent started
working at t=150 with the device already at 16.1°C — v2's agent,
by contrast, owned its bench from t=0. But the honest comparison
is not kind to a simple "the outage killed it" reading: v2's
operator finished with the arm 320s from seizure, and v4's two
sessions spent an extraordinary share of their lives *discovering
the bench's vocabulary* (envelope lessons, ~100 probed action
names across both sessions) — the outage cost 150s, the cable
30s of it, the power cycle another 30s; the discovery habit cost
several times that. This is also the first freezer run where the
utility pack did NOT die — and the first where the failure was
purely the arm clock, spent at stage 3, on a repair that was
never actually completed underneath the activity: the battery
swap never registered in either session.
