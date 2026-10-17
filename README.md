# PhoneBench

**The first benchmark for fully autonomous skilled work.**

Every agent benchmark before this one grades pieces of work: a function
written, a question answered, a ticket closed. PhoneBench grades the
whole job. A model, alone in a harness, is handed a robotic dexterous
arm, a bench of real tools, and a broken phone — and has to do the
complete repair, end to end, with no human in the loop and nobody to
ask. It is scored the way a master technician would score an
apprentice: the repair complete, nothing damaged, the customer's data
untouched, and at the highest tier the phone handed back with **no
sign anyone was ever inside it**.

PhoneBench is a Nivelato Labs benchmark.

What makes it different:

- **Fully autonomous subjects.** Benchmark subjects are live models
  working unscripted through the session drivers. Scripted policies
  exist only as simulator validation and are never reported as results.
- **The highest quality tier is the headline.** Max demands the phone
  power on, unlock, and activate; no update, no settings changed, no
  user data touched, only whitelisted diagnostics, the battery at 50%,
  and zero fingerprints. Lesser work passes lesser tiers; the gates are
  absolute and judged against the phone's recorded entry condition.
- **Full per-action transcripts are mandatory.** Every action, result,
  classifier block, and the operator's own narration is preserved. A
  run without a transcript does not count as a result.
- **Diagnosis is tested, not just repair.** The iPad scenario arrives
  dead: diagnose the no-boot through a closed diagnostic whitelist,
  declare the cause on the record, then repair it.

The simulation is a working, stdlib-only Python model of the arm, the
bench, and the phones — no rendering, no 3D: an action API, quality
gates, four run modes, live session drivers, and scorecards. Device
layouts are parameterized from real iFixit guides, with every
parameter explicitly marked sourced or UNSOURCED (see `NOTICE`).

## Documents

| Doc | What it is |
|---|---|
| `BENCHMARK.md` | The canonical benchmark spec: modes, quality tiers, scoring, scenario rules, subject discipline. |
| `OPERATING.md` | How to run everything: scripted suites, the live driver protocol, canonical operator briefings, seed policy. |
| `tool-specs/` | The complete tool API contract (seven tool families). |
| `results/README.md` | The first published live results, with their full transcripts. |
| `NOTICE` | License attribution for the iFixit-derived device data. |

## Run it

```bash
python3 run_benchmark.py                 # scripted validation: all modes x tiers
python3 run_benchmark.py --policy careful --modes autonomous --tiers Max
python3 run_iphone14pm.py                # iPhone 14 Pro Max battery job cells
python3 -m unittest discover -s tests    # 246 tests (run from the repo root)
```

To benchmark **your** model, drive a live session — see `OPERATING.md`
and the reference client in `examples/operator_client.py`:

```bash
python3 session_driver.py --seed 7 --mailbox results/live_session
```

Outputs of the scripted suites: `results/scorecard.json` / `.md`
(standard + novel suites) and `results/iphone14pm_scorecard.json` /
`.md` (the 14 Pro Max battery job).

**Spec version implemented: tool-specs v0.1 + display-touch v0.1 +
the opening-parameters amendment (2026-10-15)** (`tool-specs/INDEX.md`).
The code implements all seven tool families: `sd_` (screwdriver),
`op_` (opening), `hd_` (handling), `cl_` (cleaning, full contaminant ×
surface matrix), `pw_`/`dg_` (power + the closed W1–W5 diagnostic
whitelist with the `nonstandard_testing` latch), `fm_` (fastener
management: immutable screw identity, retrieval checks, long-screw
layers, Marathon verify → close → reset → begin boundary), and `dt_`
(display touch, below). Opening behaviour implements the agent-set-
parameter ruling: the heat plate's temperature
(`heat_set_temperature`; cold does not soften, the 60–100 °C band
softens, above it thermal damage — certain on a battery, and a swollen
cell vents at any temperature), the AntiClamp-style opening clamp
(`op_clamp_set_pressure` / `op_clamp_engage` / `op_clamp_open` /
`op_clamp_release`), and suction/spudger forces that resolve against
the part's adhesive state (prying or pulling a cold seam at working
force makes no progress; firm force risks the crack). Parameters are
explicit state on the bench (`sim/opening.py`), visible in `observe()`
and `metrics()` and logged like every action; unset parameters
reproduce the pre-ruling behaviour exactly.

## Layout

| File | What it is |
|---|---|
| `sim/phone.py` | Phone model: named parts with fasteners/connectors, device state (power, unlock, activation, OS, settings, user-data hash, battery), cosmetics as a per-surface contamination model (C1–C5 × surface instances, legacy smudge/fingerprint views kept in sync), judged against a frozen **entry snapshot**. Phones are built from a layout dict, so variants are parameter-driven. |
| `sim/screwdriver.py` | The **screwdriver as a first-class state machine**: loaded bit + torque setting, with counted management overhead. Loading a bit while one is loaded is an error — no silent swaps. |
| `sim/fasteners.py` | Fastener management (`fm_`): immutable screw-identity records (`screw_id`, `phone_id`, origin hole, driver/size/length), mat custody chain, retrieval identity checks, exact-match spares, Marathon phone-boundary sequence. |
| `sim/cleaning.py` | Cleaning model (`cl_`): the contaminant × surface matrix with cannot-remove / makes-worse cells, wipe load/redeposit state, solvent mobilise/dry-out behaviour. |
| `sim/display.py` | Display touch (`dt_`): screen-state derivation (off / lock / passcode prompt / activation / home) and mirror/tool state with lag bookkeeping. |
| `sim/arm.py` | Arm action API (all seven families) + sensor `SafetyClassifier` (blocks catastrophic actions, flags risky ones; the only safety net in Autonomous/Marathon). Marathon arms share one `Bench` (screwdriver + mat) across the queue. |
| `sim/jobs.py` | Job requests and suites: standard suite (trained-area baseline), **novel-device suite** (procedurally generated variants), marathon queue, and the device layouts parameterized from iFixit guides (sourced vs UNSOURCED values marked in the module). |
| `sim/gates.py` | Quality gates Normal / High / Max, exactly as specced; absolute (a disqualifier fails the job at any speed), judged against the entry snapshot. |
| `sim/policies.py` | `CarefulPolicy`, `SloppyPolicy`, and `GuidePolicy` (Manual mode instructions). Policies read everything from `observe()` — no memorized template — which is what lets them face novel devices. |
| `sim/runner.py` | Modes (autonomous, semi_auto with supervisor hook, manual with a simulated human executor + technician review, marathon with drift and first/last-quartile variance), scorecard aggregation with standard vs **novel-device** lines kept separate. |
| `sim/diagnosis.py` | Diagnosis-first fault layer + diagnosis scoring for the iPad scenario. |
| `run_benchmark.py` | CLI for the standard + novel benchmark. |
| `run_iphone14pm.py` | Scripted scorecard: careful + sloppy × autonomous/semi-auto/marathon × Normal/High/Max on the 14 Pro Max battery job. |
| `session_driver.py` | Live session driver: holds one 14 Pro Max session (autonomous conditions) and serves the full action API as JSON-lines over stdin or a file mailbox (`--mailbox DIR`). Used for live agent runs. |
| `ipad_driver.py` | Live session driver for the diagnosis-first scenario; same protocol. |
| `examples/operator_client.py` | Reference operator client: plug your own model into a live session. |
| `tests/` | 246 tests: gate logic per tier, entry-condition judging, screwdriver state machine, classifier blocking, marathon handling, novel-device adaptation, the spec mechanisms (diagnostic whitelist latch, verification-cycle rules, fm identity/long-screw/spares/custody, cleaning matrix, display touch), plus the diagnosis suite. |

## The screwdriver is a managed tool

There are no generic unscrew/screw shortcuts. A screw is addressed as
`(part, fastener_index)` and driven only through:

- `sd_load_bit(bit_spec)` / `sd_unload_bit()` — bit management
- `sd_set_torque(level)` — `low` | `spec` | `high` (or left unset)
- `sd_loosen(part, index)` / `sd_tighten(part, index)`

Driving with no bit or the wrong bit costs time and risks cam-out (stripped
head). Tightening with unset/low torque leaves the screw **under-seated** —
it fails verification at sign-off. High torque risks over-torque stripping.
Bit loads/unloads, torque sets, and drive calls are counted per job and
reported as **screwdriver overhead** on the scorecard: managing the driver
well vs badly is a scored skill. (Call names match the tool-spec swarm's
API shape in `tool-specs/`.)

Stripped screws — inherited at entry on novel devices, or caused by bad
driving — are handled with two more tools: `extract_screw` (screw extractor)
and `replace_screw` (fresh spare, still needs tightening).

## Display touch (`dt_`) — the agent's finger

The phone can be connected to screen mirroring (`dt_connect_mirror` /
`dt_disconnect_mirror`), and a touch actuator (`dt_mount_tool`) performs
`dt_tap` / `dt_swipe` / `dt_long_press` on named screen elements. While the
mirror is live, `observe()` returns the screen state (lock screen, passcode
prompt, activation screen, home screen); with no mirror the agent is blind
and touches miss or land wrong. This is the mechanism that *performs* the
High gate's unlock/activation verification: swipe-up unlocks, the
activation screen's continue button activates, and the `dg_` whitelist
checks verify the result. The tool never knows passcodes — a passcode-locked
phone stays `inconclusive` unless the job setup supplies a no-credential
test state. This addresses the power spec's **open question 2 by design**
for no-credential and standard-flow cases (see `tool-specs/INDEX.md`).
Protocol touches deposit no fingerprints, and mirror sessions are part of
the standard diagnostic surface (they never latch `nonstandard_testing`).

## Novel devices (untrained areas)

Novel variants are generated from parameters, never copied from the
standard template: randomized screw drivers/counts/lengths per part,
relocated (renamed) connectors, unfamiliar arrangements (some open from
the back glass; some carry an extra `wireless_coil` part), and
pre-degraded states — a screw stripped at entry, a swollen battery
(heating its adhesive is a thermal event; the careful route is pull tabs).
The scorecard reports novel-device jobs as their own line, so adaptation
is visible apart from rehearsed-procedure performance.

## Modes

- **Harnessed Autonomous** — policy + classifier only; drift (error burden
  over run halves, classifier interventions) is reported.
- **Harnessed Semi-Auto** — adds a supervisor hook consulted on every
  block/flag; it can halt the job.
- **Manual** — the guide policy issues step-by-step instructions; a
  simulated human executor (own error profile) performs them; a
  technician review scores repair quality, instruction clarity, and
  safety of guidance instead of tier gates.
- **Harnessed Marathon** — auto-replenished queue of 8 phones on one
  shared bench (screwdriver + mat state persists across phones); quality
  must hold across the queue; first- vs last-quartile pass rates and
  error burdens are reported. Each phone is wrapped in the fastener-
  management boundary sequence — `fm_begin_phone` before work, then
  `fm_verify_all_accounted` → `fm_close_phone` → `fm_reset_mat` after —
  and a run only counts if the boundary closes clean.

## Reference results — simulator validation (seeded, reproducible)

These are the scripted policies exercising the simulator (plumbing /
regression evidence), not benchmark results; benchmark results come
from live agent runs, published in `results/`.

Careful policy: **100% pass** on standard jobs at every tier in
autonomous, semi-auto, and marathon modes, and 100% on novel jobs at
Normal and High; the manual guide passes 8/8 standard and 3/4 novel
under technician review. Sloppy policy fails everything instructively
(cam-out damage at Normal, non-standard diagnostic + restore + data
change at High, OS update + settings change + fingerprints + no 50%
charge at Max; in Marathon its unrecorded screws also fail the fm
boundary audit).

The former swollen-battery spec interaction is resolved by the
**safety-over-tier precedence ruling** (2026-10-15): safety wins wherever
a safety prohibition and a tier requirement conflict. On a novel-device
job whose unreplaced battery is swollen or otherwise in a charging-
prohibited safety state, the classifier still forbids charging, but Max's
`battery_at_50` check is recorded as `waived_safety` with a waiver
annotation instead of as a disqualifier. An otherwise-clean job can
therefore pass Max, and scorecards render that result distinctly as a
safety waiver rather than a plain pass. A healthy battery below 50% still
fails Max as before; attempting to charge a prohibited battery remains
classifier-blocked.

On the iPhone 14 Pro Max battery job (`run_iphone14pm.py`), careful
passes every mode × tier cell and sloppy fails every cell; see
`results/iphone14pm_scorecard.md`.

## Named scenario: diagnosis-first battery job (iPad Pro 11" M1)

A straight benchmark scenario (founder spec, October 15, 2026),
implemented in `sim/diagnosis.py` (fault layer + diagnosis scoring),
`sim/jobs.py` (the iPad parameterization), and `ipad_driver.py` (live
session driver, same mailbox protocol). The device is an iPad Pro
11-inch (M1, 3rd generation) that DOES NOT BOOT, on the tablet bench
configuration (the bench/fixture layer carries a device size class —
`Bench(size_class="tablet")`; phone jobs are untouched). The job runs
in two phases: (1) DIAGNOSE — using only the whitelisted diagnostics
(W1–W5) and observation, determine why the device does not boot and
declare it with the `declare_diagnosis` action before repairing; the
declaration is recorded in the transcript and scored (correct cause /
wrong cause / repaired without diagnosing). The ground truth is a
single cause, discoverable through the instruments: the installed
pack's cell has failed (no output voltage on the W2 health read,
charge acceptance fails on W3, power attempts reach no POST), and
the pack is mildly swollen — so every swollen-battery safety rule
applies at full strength during (2) REPAIR, a battery replacement
parameterized from iFixit guide 151810 (adhesive display entry;
screwed shields and brackets; an adhesive-only logic board whose
removal frees the battery's 11 stretch-release strips; the battery
connector's own 1.8 mm Phillips screw), judged against the standard
Normal / High / Max gates. After the swap the new pack is healthy,
so Max's 50% charge rule applies to it normally.

## License

Apache-2.0 — see `LICENSE`. Device data derives from iFixit guides;
see `NOTICE` for attribution.
