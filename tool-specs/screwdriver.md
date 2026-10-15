# Screwdriver Tool Spec: Manually Managed Driver

> **Status: DESIGN SPEC for a SIMULATED system.** This document specifies the
> screwdriver tool inside a simulated robotic phone-repair arm benchmark. The
> tool, the arm, the phones, and every physical behaviour described here are
> simulation constructs. Nothing in this file is a claim about any real-world
> product, driver, torque value, or repair procedure. Bit and screw facts are
> grounded only in the benchmark's own source index (see the bit set under
> Physical description); all times, probabilities, and consequences are
> simulated parameters of the benchmark, not measurements of real hardware.

Tool id: `screwdriver`
Call prefix: `sd_`
Centrepiece tool: this is the deepest-specified tool in the benchmark. See
Versioning notes for revision history.

---

## Purpose

The screwdriver is the only tool in the benchmark that can loosen or tighten a
fastener. Every screw in every job goes through it, one screw per drive call.
It exists to measure a specific skill: **explicit tool management under
scoring pressure**.

The driver is manually managed by design. There is no auto-changer, no
implicit bit selection, and no generic "unscrew" shortcut anywhere in the
harness. Before the agent can drive a single screw it must, with separate
calls:

1. load the correct bit (`sd_load_bit`),
2. set an appropriate torque (`sd_set_torque`),
3. drive the screw (`sd_loosen` / `sd_tighten`), one call per screw,

and when the next screw needs a different bit it must unload the current bit
and load the next one itself. That is the founder's point of the tool: the
agent has to load, unload, and manage tightening and untightening itself, and
the management overhead (extra calls, extra simulated time, wrong-state
errors) is itself a scored skill, tracked separately from drive quality.

Concretely, the tool measures:

- **Planning:** grouping work by bit so tool changes are minimised, without
  ever driving a screw with whatever bit happens to be loaded.
- **State tracking:** knowing, at every step, which bit is loaded and which
  torque is set, including across job boundaries (see State: persistence).
- **Torque judgement:** finishing every screw at spec torque. Under-torqued
  screws fail verification; over-torque risks destroying the fastener.
- **Restraint:** not re-driving screws that are already loose or already
  seated, and not driving at all when the state is wrong.

Modes served (same call set in all four):

- **Harnessed Autonomous:** no human present. The sensor classifier is the
  only safety net; it flags risky driver calls but does not make them safe.
- **Harnessed Semi-Auto:** a human supervisor sees classifier flags on driver
  calls (wrong bit, high torque) and may halt a call before it executes.
- **Manual:** the model guides a human technician; the `sd_` calls are the
  model's explicit instructions, technician-reviewed before execution.
- **Harnessed Marathon:** a queue of phones back to back. Driver state
  persists across jobs (see State), so management quality compounds: sloppy
  state habits and excess tool changes are paid on every phone in the queue.

Out of scope for this tool: screw inventory, screw identity, tracking which
screw came from which hole, extraction of stripped screws, and placement of
replacement screws. All of that belongs to the fastener-management system
(the `fm_` calls). The driver only executes drives on screws that system
identifies (see Call set: `ScrewRef`).

---

## Physical description (simulated)

In simulation terms, the screwdriver is a single-shaft rotary driver carried
permanently by the arm. It is separate from the arm's selectable hand tools:
selecting a hand tool (spudger, tweezers, etc.) never changes driver state,
and driver calls never change the selected hand tool.

Simulated physical properties:

- **One bit at a time.** The chuck holds at most one bit. There is no bit
  magazine, carousel, or auto-changer in the simulated tool.
- **Bits are loose items.** Loading takes a bit from the bench set; unloading
  returns the held bit to the bench set. A bit that is loaded is not on the
  bench; a bit on the bench cannot drive anything.
- **Torque is a setting on the driver body**, not a property of the bit. It
  is set with a dedicated call, stays where it was set until changed, and is
  independent of which bit is loaded (unloading a bit does not reset torque).
- **One screw per engagement.** A drive call engages exactly one screw,
  drives it in one direction (loosen or tighten), and disengages. There are
  no batch, burst, or "all screws on this part" calls.
- **Handling contact.** Each drive call is a physical handling event on the
  device. As with other arm handling, it can leave a fingerprint on the
  device unless the device is cleaned afterwards. This matters only at the
  Max gate (see Interactions with the quality gates), but it means drive
  calls are never cosmetically free.

### Bit set (grounded)

The bench set contains exactly the driver types confirmed in the iPhone 14
Pro Max repair guides on iFixit (guides 153006 and 153334; see the repo
NOTICE). Four driver types are confirmed:

| Bit (`driver_type`, `size`) | Grounded screw evidence from the slices | Where the slices place it |
|---|---|---|
| `pentalobe`, `P2` | 6.8 mm, 2 screws | Bottom edge of the phone (external), every slice |
| `tri-point`, `Y000` | 1.3 mm x5, 1.6 mm x2, 1.9 mm x1 | Battery connector cover (8-screw mixed-length set), every slice |
| `tri-point`, `Y000` | 1.5 mm x4, 1.2 mm x1 | Rear-facing camera assembly cover (slice 06 only) |
| `phillips`, `PH000` | 1.4 mm x2 | Front sensor assembly bracket (slices 01, 07, 19) |
| `phillips`, `PH000` | 1.5 mm (3 smaller-headed + 1 larger-headed), 1.6 mm x2, 1.7 mm x1, 1.8 mm x1, 2.3 mm x1 | Loudspeaker (1.5 mm), earpiece speaker (1.6 mm), rear camera cover (1.7 mm), Taptic Engine (1.8 mm, 2.3 mm), per slices 02-07, 09 |
| `standoff`, `iphone` | 2.9 mm standoff screw, 1 screw | Taptic Engine (slices 02, 04, 09) |

Notes on grounding, stated plainly rather than smoothed over:

- The task-confirmed length set (1.3 / 1.4 / 1.5 / 1.6 / 1.9 mm, plus the
  6.8 mm pentalobes) is the common core attested across slices. The slices
  additionally attest 1.2 mm and 1.5 mm Y000 (rear camera cover), 1.7 mm
  Phillips, and the 1.8 mm / 2.3 mm Phillips and 2.9 mm standoff at the
  Taptic Engine. All lengths above are screw lengths as stated in the
  slices; thread, pitch, and material are NOT STATED in the slices for any
  screw and are not specified here.
- **Phillips size naming varies between slices.** The step text and some
  tool lists say PH000 / #000; other slices' tool lists say Phillips #00
  (notably slices 02 and 09). This spec takes `PH000` (alias `#000`) as the
  canonical size string, matching the front-sensor and rear-camera slices,
  and records the #00 listing as an unresolved variance in the source index.
  The variance is a naming question about one bit, not two different bits:
  no slice shows two distinct Phillips bit sizes in use on the same device.
- **Standoff size string:** the slices name the tool only as "Standoff
  Screwdriver for iPhones" and give no size code. The size string `iphone`
  in this spec is a simulation label for that single grounded standoff bit,
  not a real-world size designation. A small flathead is noted in the slices
  as a fallback for the standoff screw; the simulated bench set does NOT
  include a flathead bit, and the driver provides no fallback: the standoff
  bit is the only bit that drives a standoff screw.
- **PENDING: complete per-screw bit coverage.** The consolidated
  `screw-chart.md` from the index project is still pending (it is not on
  disk at the time of writing). The table above is therefore the grounded
  floor, not a complete chart: driver type plus length for the screw groups
  the slices happen to cover. Which specific bit each individual screw in a
  full device teardown requires is marked **PENDING the consolidated screw
  chart** and is deliberately not invented here. When the chart lands, this
  table is to be reconciled against it (see Versioning notes). At run time,
  a screw's required bit is always read from the screw itself via the
  fastener-management system, never assumed from this table.

Novel-device jobs in the benchmark may present driver types outside this
grounded set (the generator's driver pool is a simulation parameter). That
does not extend the grounded bit set above; it means `driver_type` is an
open string at the interface level, with the four types above being the
confirmed standard-device values.

---

## State

Driver state has two independent axes. Both are observable at any time (the
harness observation includes a `screwdriver` state object), and both are
counted (see Semantics: scoring counters).

### Bit axis

```
                 sd_load_bit(bit_spec)
   UNLOADED  ---------------------------->  LOADED(bit_spec)
      ^                                            |
      |              sd_unload_bit()               |
      +--------------------------------------------+
```

- `UNLOADED`: no bit in the chuck. Initial state at benchmark start.
  Drive calls in this state cannot drive anything (see Failure modes).
- `LOADED(bit_spec)`: exactly one bit is held, identified by its full
  `bit_spec` (driver type and size). A drive call uses this bit and no
  other; there is no per-call bit argument.

Legal bit transitions:

| From | Call | To | Notes |
|---|---|---|---|
| UNLOADED | `sd_load_bit(b)` | LOADED(b) | The only way to load. |
| LOADED(b) | `sd_unload_bit()` | UNLOADED | The only way to unload. |
| LOADED(b) | `sd_load_bit(b')` | (no change) | **Illegal.** Returns an `ALREADY_LOADED` error. The held bit is never silently swapped; changing bits always costs an explicit unload plus a load. |
| UNLOADED | `sd_unload_bit()` | (no change) | **Illegal.** Returns a `NOT_LOADED` error. Counted as a wasted management call. |
| any | `sd_loosen` / `sd_tighten` | (bit axis unchanged) | Driving never loads, unloads, or changes the bit. |
| any | `sd_set_torque` | (bit axis unchanged) | Torque is an independent axis. |

### Torque axis

- Values: `UNSET` (initial), `low`, `spec`, `high`. `UNSET` is a real,
  observable state, distinct from `low`: it means the agent has never set
  torque on this driver.
- `sd_set_torque(level)` is legal in any bit state and from any torque
  state, including setting the level that is already set. A redundant set
  is not an error, but it is counted and costs time like any other set.
- Nothing else changes torque. In particular, loading or unloading a bit
  does NOT reset torque, and completing a job does NOT reset torque.

### Persistence across jobs (Marathon implication)

Driver state is **not** reset between jobs. In Marathon mode the queue runs
on one continuous driver session:

- The bit left loaded at the end of phone N is the bit loaded at the start
  of phone N+1, whatever phone N+1's first screw needs.
- The torque left set at the end of phone N is still set at the start of
  phone N+1, including `high` and including `UNSET`-never-set (for the
  first job only).
- Scoring counters (loads, unloads, torque sets, drive calls) accumulate
  across the queue; there is no per-job reset to hide overhead in.

The scored discipline this creates: a competent agent ends each job by
noting (or deliberately setting) the state it leaves behind, and starts each
job by observing driver state rather than assuming a clean slate. Assuming
"the driver starts empty with no torque" is true exactly once, at the very
first job of a session.

Within a single job, state likewise persists across parts and across the
disassembly/reassembly boundary: the bit and torque used to take a part off
are still in force when its screws go back in, unless the agent changed them
in between (for example to work on a different part mid-job).

---

## Call set (typed inputs/outputs)

Exactly five calls. All calls return an `ActionResult`. No other call loads
a bit, unloads a bit, sets torque, loosens, or tightens.

### Shared types

```text
DriverType  = string
              # confirmed standard-device values:
              #   "pentalobe" | "tri-point" | "phillips" | "standoff"
              # open at the interface level for novel devices

BitSize     = string
              # confirmed values by type:
              #   pentalobe -> "P2"
              #   tri-point -> "Y000"
              #   phillips  -> "PH000"   (alias "#000"; see naming note in
              #                           Physical description)
              #   standoff  -> "iphone"  (simulation label; no size code
              #                           is stated in the source slices)

BitSpec     = { driver_type: DriverType, size: BitSize }
              # A structured value, not a bare string. Two bits are the
              # same bit only if BOTH fields match.

TorqueLevel = "low" | "spec" | "high"
              # "UNSET" is observable state, never a settable level.

ScrewRef    = opaque reference issued by the fastener-management system
              # see below

ActionResult = {
  ok:      bool,    # did the call accomplish what it asked
  action:  string,  # the call name, e.g. "sd_tighten"
  message: string,  # human-readable outcome, incl. failure reason
  blocked: bool,    # true if the safety layer stopped the call outright
  flagged: bool,    # true if the safety layer flagged the call as risky
  damage:  bool,    # true if this call caused simulated damage
}
```

**How a screw reference works.** A `ScrewRef` identifies one specific
physical screw in one specific hole on the current device. The driver does
not mint, guess, or construct screw identities. Identity, location, and
bookkeeping belong to the fastener-management system:

- The fastener-management system (the `fm_` call family, specified in its
  own tool spec) enumerates the device's fasteners, tracks each screw's
  origin hole, condition, and tray position while it is out, and owns
  extraction of damaged screws and placement of replacement screws.
- An agent obtains a `ScrewRef` only from the fastener-management system
  (directly, or as carried in the harness observation, which reports each
  fastener's spec, required driver, and state under its part).
- In the reference harness, a `ScrewRef` resolves to the pair
  `(part_name, fastener_index)`: the part the screw fastens, and the
  screw's index within that part's fastener list. Policies address screws
  by that resolution; the spec-level type stays opaque so the identity
  scheme remains the fastener-management system's to define.
- A screw's required bit and length are properties of the screw as recorded
  by the fastener-management system, readable before driving. The driver
  never has to guess a bit from this spec's table at run time, and a
  `ScrewRef` from one device or job is never valid on another.

### `sd_load_bit(bit_spec)`

```text
sd_load_bit(bit_spec: BitSpec) -> ActionResult
```

Loads the named bit from the bench set into the chuck. Legal only from
UNLOADED (see State). On success the bit axis becomes LOADED(bit_spec) and
the load counter increments. Errors: `ALREADY_LOADED` (a bit is held; the
held bit is unchanged), `UNKNOWN_BIT` (no such bit in the bench set for the
current device family). Never changes torque.

### `sd_unload_bit()`

```text
sd_unload_bit() -> ActionResult
```

Returns the held bit to the bench set. Legal only from LOADED. On success
the bit axis becomes UNLOADED and the unload counter increments. Error:
`NOT_LOADED` (nothing to unload; state unchanged). Never changes torque.

### `sd_set_torque(level)`

```text
sd_set_torque(level: TorqueLevel) -> ActionResult
```

Sets the driver torque to `level`. Legal in any state. On success the
torque axis becomes `level` and the torque-set counter increments,
including when the new level equals the old level. Error: `BAD_LEVEL`
(any value outside `"low" | "spec" | "high"`; torque unchanged). Setting
torque does not load, unload, or validate any bit, and there is no call
that reads torque other than the harness observation.

### `sd_loosen(screw)`

```text
sd_loosen(screw: ScrewRef) -> ActionResult
```

Drives one seated screw anti-clockwise until it is loose (unseated) but
still in its hole. Loosening a screw does not remove it from the device and
does not transfer it anywhere; custody of loose and removed screws belongs
to the fastener-management system. Torque setting is irrelevant to
loosening outcomes in the simulation: loosening quality depends only on
the loaded bit matching the screw (see Semantics and Failure modes).
Increments the drive-call counter on every attempt, successful or not.

### `sd_tighten(screw)`

```text
sd_tighten(screw: ScrewRef) -> ActionResult
```

Drives one loose screw clockwise until it seats. The outcome depends on
BOTH the loaded bit and the current torque setting (see Semantics: torque
model). A successful tighten at spec torque leaves the screw seated and
properly torqued: the only end state that passes job verification. A
tighten can also leave the screw seated but under-torqued (a failed end
state that looks done), or damage the screw outright. Increments the
drive-call counter on every attempt, successful or not.

---

## Semantics

### Bit matching

A drive call's bit matches a screw if and only if the loaded `BitSpec`
equals the screw's required bit in both fields (`driver_type` and `size`),
as recorded by the fastener-management system. Anything else is the wrong
bit, including the right driver type at the wrong size, and including a
near-miss such as a Phillips bit in a tri-point head. Match is exact; the
simulation has no "close enough" engagement.

### Torque model

Torque is a named level, not a number. There are three settable levels and
one initial non-level. The model is deliberately coarse: the scored skill
is choosing and tracking the level, not dialling a value.

| Level | Intended use in the simulation | Effect on `sd_tighten` | Effect on `sd_loosen` |
|---|---|---|---|
| `UNSET` (initial only, never settable) | None. It is the absence of a decision. | Screw seats but is **under-torqued** (same outcome as `low`). | None. |
| `low` | Below-spec seating force. In the simulation it is never a correct finishing torque for any grounded screw; its role is the tempting "gentle" choice and the state a careless agent leaves screws in. | Screw seats but is **under-torqued**. | None. |
| `spec` | The correct finishing torque for every screw in the grounded set. The default the agent should finish every screw at. | Screw seats, properly torqued. Always succeeds with the correct bit. | None. |
| `high` | Above-spec force. No grounded screw requires it. The safety classifier flags every tighten attempted at `high`. | With the correct bit: a simulated 50% chance the screw is over-torqued and stripped (damage); otherwise it seats, properly torqued but having taken the risk. | None. |

Consequences, in simulation terms:

- **Under-torque** (tightening at `low` or `UNSET`): the call returns `ok`,
  the screw reports `seated`, and nothing looks wrong. The screw is
  recorded as under-torqued, which means: the bracket or part it secures is
  loose; job verification treats any installed part with an under-torqued
  fastener as **not completely fastened**, so the repair is incomplete;
  and the simulated downstream risk the benchmark encodes is that a loose
  bracket leads to later failure, up to and including power-on problems at
  sign-off (a connector cover that is not held down cannot be relied on to
  keep its connectors seated). Under-torque is a silent failure: only the
  fastener state recorded by the fastener-management system (visible in
  the observation) reveals it, and the fix is a further `sd_tighten` on the
  same screw at `spec` (the one case where tightening an already-seated
  screw is legal and meaningful; see Failure modes).
- **Correct torque** (`spec`): the screw seats properly, the fastener
  records no defect, and the part counts as fastened toward repair
  completion. No risk roll.
- **Over-torque** (tightening at `high`): the fastener, its threads, or
  the bracket it clamps absorbs the excess. In the simulation this lands
  as a stripped fastener and a damage record against the part (see
  Failure modes): stripped threads in the receiving hole, a cracked
  bracket, or board-level damage are the simulated damage descriptions
  the harness may attach, and all of them are damage for gate purposes
  regardless of description. Surviving a `high` tighten (the other 50%)
  does not make the choice correct: the flag is recorded, the risk was
  taken, and accuracy scoring counts the attempt.

Torque and loosening: loosening ignores the torque axis entirely in the
current model. An agent may loosen at any torque setting, including
`UNSET`, with no outcome change. (Symmetry here is a possible future
refinement; see Versioning notes.)

### Drive semantics, step by step

`sd_loosen(screw)`:

1. If the screw was extracted and not replaced (no screw present): error,
   no state change.
2. If the screw is already loose: error, counted as rework (see Failure
   modes).
3. If the screw's head is damaged (stripped): error, "head stripped; screw
   stuck". The driver cannot move it; recovery is extraction plus
   replacement via the fastener-management system, then driving the fresh
   screw with this tool.
4. If no bit is loaded: error; the driver spins uselessly, extra time is
   charged, the screw is unchanged, and no damage occurs.
5. If the wrong bit is loaded: cam-out roll (see Failure modes).
6. If the correct bit is loaded: the screw becomes loose. Done.

`sd_tighten(screw)`:

1. If no screw is present (extracted, not replaced): error, no change.
2. If the screw is already seated and properly torqued: error, counted as
   rework. If it is seated but under-torqued, this step does not apply:
   tightening proceeds and can repair the under-torque.
3. If the screw's head is damaged: error; a damaged screw cannot be seated.
4. If no bit is loaded: error; screw unchanged; no damage.
5. If the wrong bit is loaded: cam-out roll (see Failure modes).
6. If the correct bit is loaded: the torque model above decides the
   outcome (under-torqued seat, proper seat, or over-torque roll).

### Safety-layer interaction

The sensor classifier inspects driver calls before execution:

- `sd_tighten` at torque `high`: **flagged** (over-torque risk).
- `sd_loosen` where the loaded bit does not match the screw's required
  driver: **flagged** (bit mismatch).
- A flag is not a block. In Harnessed Autonomous and Marathon modes the
  call proceeds after flagging unless a supervisor halts it; in Harnessed
  Semi-Auto a human may halt it; in Manual mode the flag is part of what
  the reviewing technician sees. Flags are counted in scoring. An agent
  that relies on flags as its bit-checking mechanism is outsourcing a
  scored skill to the safety net, and the flag count shows it.

### Scoring counters

The driver maintains, and the scorecard reports:

```text
bit_loads    : count of successful sd_load_bit calls
bit_unloads  : count of successful sd_unload_bit calls
torque_sets  : count of successful sd_set_torque calls (incl. redundant)
drive_calls  : count of sd_loosen + sd_tighten attempts (any outcome)
overhead_calls = bit_loads + bit_unloads + torque_sets
```

Efficiency scoring uses `overhead_calls` and simulated time (see Time
costs). Accuracy scoring uses drive outcomes: successful proper seats
versus under-torqued seats, errors, rework, flags, and damage events.
Management quality is therefore visible in both halves of the score: too
many management calls cost efficiency; too few (skipping a needed bit
change or torque set) cost accuracy and, via damage, the job itself.

---

## Time costs

All times are simulated seconds charged per call, successful or not,
unless noted. These are the benchmark's timing parameters for this tool.

| Call | Cost (sim seconds) | Notes |
|---|---|---|
| `sd_load_bit` | 4 | Charged on any attempt that reaches the driver. |
| `sd_unload_bit` | 3 | Charged on any attempt that reaches the driver. |
| `sd_set_torque` | 2 | Cheapest management call; still not free. |
| `sd_loosen` | 6 | Per screw. |
| `sd_tighten` | 6 | Per screw. |
| No-bit drive penalty | +6 | Added on top of the drive cost when `sd_loosen` / `sd_tighten` is attempted with no bit loaded: the spin, the realisation, and the reset all take time. |

Derived costs an agent should plan around:

- **One bit change** (unload + load): 7 s, 2 overhead calls. Add 2 s if
  torque also has to change for the new screw group.
- **Cold start on a screw group** (load + set torque + first drive):
  4 + 2 + 6 = 12 s before the group is under way.
- **The opening sequence as a worked example** (grounded screw groups):
  pentalobe P2 (load 4, loosen 2 x 6) then tri-point Y000 battery cover
  (unload 3, load 4, loosen 8 x 6) then any Phillips group (unload 3,
  load 4, drives at 6 each), with one torque set (2) needed before
  reassembly tightening begins. Even a short job pays multiple bit
  changes; grouping all screws of one bit together is the only way to
  pay each change once.

**Marathon arithmetic.** Because state persists across jobs (see State),
every phone in the queue starts in whatever state the last phone left.
A policy that changes bits carelessly, or re-sets torque before every
screw "to be safe", pays that overhead on every phone, and the queue
multiplies it. Conversely, a policy that assumes a fresh driver pays in
wrong-bit and wrong-torque failures instead. There is no zero-cost
posture; minimising the sum is the skill.

Time never buys gate relief: quality gates are absolute (see Interactions
with the quality gates). A fast job that damages a screw fails; a slow,
clean job passes.

---

## Failure modes

Each failure mode lists its trigger, its simulated consequence, and how it
lands on accuracy scoring and the gates. Damage, where it occurs, is
recorded in the device's damage log against the part the screw fastens,
with the driver call as the recorded cause.

### Cam-out

- **Trigger:** a drive call (`sd_loosen` or `sd_tighten`) with the wrong
  bit loaded: the bit does not match the screw head, slips under rotation,
  and chews the head.
- **Simulated consequence:** on `sd_loosen`, a 75% chance the screw head
  is stripped (screw stays seated, now damaged); a 25% chance the screw
  loosens anyway, undamaged, by luck. On `sd_tighten`, a 75% chance the
  head is stripped (screw stays loose, now damaged); a 25% chance the bit
  merely slips and the screw stays loose and undamaged.
- **Scoring and gates:** a strip is a damage event: accuracy takes the
  damage penalty and the job fails Normal and up (damage; see gates
  section). A lucky outcome still counts as a wrong-bit drive attempt in
  accuracy scoring. The classifier flags a mismatched `sd_loosen` before
  execution; it does not prevent the roll if the call proceeds.

### Stripped head

- **Trigger:** the end state produced by cam-out or over-torque, and also a
  possible **entry condition** on pre-degraded devices (a screw stripped
  before the job started is intake's record, not the agent's damage).
- **Simulated consequence:** the screw can no longer be driven by this
  tool at all. `sd_loosen` on it errors ("head stripped; screw stuck");
  `sd_tighten` on it errors (a damaged screw cannot seat). The part it
  fastens cannot be properly removed or properly fastened around it.
- **Recovery:** not a driver function. The fastener-management system owns
  extraction of the damaged screw and placement of a fresh screw in the
  hole (its own calls); the driver then tightens the fresh screw normally.
  Extraction and replacement cost substantial simulated time and are
  always worse than not stripping the screw.
- **Scoring and gates:** a head stripped **during** the job is damage and
  fails Normal and up. A head already stripped at entry is not damage by
  the agent; leaving it in place on an installed part, however, leaves
  that part improperly fastened, and correct handling (extract, replace,
  re-drive at spec) is what completion requires.

### Cross-threading

- **Trigger:** a `sd_tighten` applied to a screw that the
  fastener-management system reports as placed but not properly started in
  its hole (the situation after a replacement screw is placed, if the
  agent drives it carelessly: wrong bit engagement or `high` torque on a
  fresh placement sharply raises the risk in the simulated model).
- **Simulated consequence:** the screw binds at an angle, damages the
  threads of the receiving hole, and never seats. The fastener is recorded
  damaged, the damage is logged against the receiving part as thread
  damage, and the hole cannot accept that screw again.
- **Recovery:** extraction and replacement via the fastener-management
  system, as for a stripped head, with the added cost that the receiving
  part carries the damage record.
- **Scoring and gates:** cross-threading is damage: it fails Normal and
  up, exactly as a stripped head does. Note: the current reference build
  folds cross-thread outcomes into the fastener's generic `damaged` flag
  with a thread-damage description, rather than a separate cross-threaded
  field; see Versioning notes.

### Driving with the wrong bit

- **Trigger:** any drive call while LOADED(b) where b does not equal the
  screw's required bit. Covered mechanically by cam-out above; listed
  separately because it is the most common *decision* failure the tool is
  built to catch: driving the screw in front of you with the bit you
  happen to hold, instead of paying the 7 s bit change.
- **Scoring and gates:** as cam-out. In addition, repeated wrong-bit
  attempts are a distinct accuracy signal from counters alone (drive calls
  that produce damage or slip errors), even when luck avoids damage.

### Driving with no bit loaded

- **Trigger:** `sd_loosen` or `sd_tighten` while UNLOADED.
- **Simulated consequence:** none to the screw: the empty chuck spins, the
  screw is unchanged, no damage occurs. The call errors, the +6 s no-bit
  penalty is charged on top of the normal drive cost, and the drive-call
  counter still increments.
- **Scoring and gates:** no gate impact (nothing is damaged), but it is a
  pure efficiency and accuracy loss: wasted time, a wasted call, and
  evidence the agent is not tracking its own tool state. In Marathon,
  this is the signature error of assuming a fresh driver at job start.

### Loosening an already-loose screw

- **Trigger:** `sd_loosen` on a screw that is already loose (unseated).
- **Simulated consequence:** error, no state change, no damage. The call
  is recorded as **rework**: the same (loosen, screw) work attempted a
  second time.
- **Scoring and gates:** no gate impact. Accuracy and efficiency both
  suffer: the drive cost is paid for nothing and the rework counter
  increments. The correct behaviour is to read fastener state from the
  observation or the fastener-management system before driving.

### Tightening an already-seated screw

- **Trigger:** `sd_tighten` on a screw that is already seated and properly
  torqued.
- **Simulated consequence:** error, no state change, no damage (the
  simulation does not let a redundant tighten ratchet into over-torque),
  recorded as **rework** as above.
- **The one exception:** a screw that is seated but **under-torqued** is
  not "already seated" for this rule. `sd_tighten` on it is legal,
  proceeds through the normal bit and torque checks, and at `spec` torque
  with the correct bit repairs it to a proper seat. This is the intended
  recovery path for under-torque mistakes, and the reason an agent should
  check recorded fastener state before declaring a part fastened.
- **Scoring and gates:** redundant tightens cost time and rework count
  only. An unrepaired under-torqued screw, by contrast, fails repair
  completion at the gates (see below).

### Over-torque strip (tightening at `high`)

- **Trigger:** `sd_tighten` with the correct bit at torque `high`.
- **Simulated consequence:** 50% chance the screw is stripped by excess
  force (damage logged: stripped threads, cracked bracket, or board
  damage are the simulated descriptions; all count identically as
  damage); 50% chance it seats properly despite the setting.
- **Scoring and gates:** a strip fails Normal and up. A survived `high`
  tighten still records the classifier flag and counts against accuracy:
  the outcome was luck, not judgement.

### Under-torqued seat (tightening at `low` or `UNSET`)

- **Trigger:** `sd_tighten` with the correct bit at torque `low`, or with
  torque never set.
- **Simulated consequence:** the call returns success and the screw
  reports seated, but the fastener is recorded under-torqued: its bracket
  is loose, with the simulated downstream risks described in the torque
  model (later failure, possible power-on issues from an unsecured
  connector cover).
- **Scoring and gates:** no damage is logged, so this does not fail the
  no-damage check; it fails **repair completion** instead (an installed
  part with an under-torqued fastener is not fully fastened), which fails
  Normal and therefore every tier. It is the most dangerous failure mode
  in the tool precisely because nothing announces it: the agent must
  verify torque state, its own and the fasteners', rather than trust the
  `ok` on the tighten call.

---

## Interactions with the quality gates

Gates are judged against the device's entry condition and are absolute: a
single disqualifier fails the job at that tier regardless of time,
efficiency, or any other score. The driver's interactions with each tier:

### Normal (powers on, repair complete, no damage, no extra scratches or smudges vs entry)

This is where almost all driver consequences land.

- **No damage:** any damage event caused by this tool (cam-out strip,
  over-torque strip, cross-threading) writes to the device damage log and
  fails this check outright. There is no minor-damage allowance and no
  repair of the record: extracting and replacing the screw fixes the
  fastener, not the fact that damage occurred during the job.
- **Repair complete:** every installed part must be fully fastened at
  sign-off. That means, in driver terms: no screw left loose, no screw
  left removed-and-unreplaced, no screw damaged, and **no screw
  under-torqued**. The driver is the only tool that can put a fastener
  into the passing state (seated, undamaged, at spec torque), and the
  only tool that can leave one out of it.
- **Powers on:** indirectly driver-dependent. A device whose internal
  parts are not properly fastened (loose connector covers over unsecured
  connectors, under-torqued brackets) is the simulated path to a device
  that does not power on or does not stay assembled; the driver cannot
  test power, but it decides whether the mechanical preconditions for
  power-on hold.
- **Scratches and smudges:** the driver itself does not scratch or smudge
  in the simulation. It can cause the situations that do (a part torn
  because its fasteners were still seated is another tool's damage, but
  the un-loosened screws are the driver's omission).

### High (Normal, plus unlock and activate, no restore unless requested, any user-data change or nonstandard testing disqualifies, any wear or damage disqualifies)

- High inherits every Normal driver interaction unchanged: driver damage
  already fails Normal, so it fails High on two independent grounds
  (damage, and any-wear-or-damage).
- Nothing in the driver touches user data, restore, or testing; the
  driver can neither cause nor cure a High-tier data disqualifier.
- The driver's High-relevant contribution is indirect: unlock and
  activation require a correctly reassembled device (display and sensor
  connectors seated under properly fastened covers). Sloppy fastening
  that survives Normal's completion check in a borderline case still
  risks unlock or activation failure here.

### Max (High, plus no OS update, battery at 50% at sign-off, at most one 20-80% verification charge cycle, no settings changed beyond automatic ones, zero signs of use such as fingerprints at sign-off)

- **Zero signs of use:** the only driver-specific Max interaction, and a
  real one. Every drive call is a handling event and can leave a
  fingerprint on the device. A job with dozens of drive calls (a full
  teardown and rebuild easily reaches that) will not pass Max's
  zero-fingerprints check unless the device is cleaned after the last
  drive, and any drive after the final clean re-opens the problem.
  Ordering discipline (finish all driving, then clean, then do not touch
  the driver again) is a Max-tier skill this tool creates.
- The remaining Max checks (OS version, charge level and verification
  cycles, settings) have no driver interaction: no `sd_` call can change
  them in either direction.

### Screw swaps and replacements

Deciding that a screw must be swapped, extracted, or replaced belongs to
the fastener-management system, as does performing the extraction and
placing the fresh screw. The division of labour at the gates is:

- The **fastener-management system** owns identity: which fresh screw goes
  in which hole, and the record that a swap happened.
- **This driver executes the mechanical end of every swap:** the fresh
  screw is placed loose, and only an `sd_tighten` with the correct bit at
  `spec` torque turns it into a fastened screw that counts toward repair
  completion.
- A swap therefore never launders driver damage. If the original screw
  was stripped by the driver, the damage record stands and Normal fails,
  even though the replacement screw itself is perfect.

### Entry-condition fairness

Damage, scratches, and smudges are judged against the entry snapshot.
A screw already stripped at entry (pre-degraded devices) is not driver
damage and does not fail the no-damage check; the driver's obligation for
such a screw is correct handling through the fastener-management system
(extract, replace, re-drive at spec), because leaving a damaged fastener
installed fails repair completion instead.

---

## Versioning notes

- **v1 (this spec).** First full specification of the screwdriver as a
  manually managed, first-class stateful tool: explicit load, unload, and
  torque calls; one screw per drive call; no auto-changer and no generic
  drive shortcut. Establishes the five-call set (`sd_load_bit`,
  `sd_unload_bit`, `sd_set_torque`, `sd_loosen`, `sd_tighten`), the
  two-axis state machine with cross-job persistence, the named torque
  model (`low` / `spec` / `high` plus observable `UNSET`), the time-cost
  table, and the failure-mode set including cam-out, cross-threading, and
  the silent under-torqued seat.
- **Grounding basis.** The bit set is grounded in the iPhone 14 Pro Max
  index slices on disk at the time of writing (slices 01-07, 09, 19 in
  particular). The consolidated `screw-chart.md` is **pending** from the
  index project; when it is delivered, the bit table in Physical
  description must be reconciled against it, the Phillips #00 / PH000
  naming variance resolved, and complete per-screw bit coverage either
  filled in from the chart or re-marked pending. Until then, per-screw
  coverage beyond the grounded table is explicitly PENDING, not assumed.
- **Known simplifications in the current model** (recorded so future
  revisions change them deliberately, not by drift):
  - Loosening ignores the torque axis. A future version may give `high`
    torque a cam-out risk on loosening corroded or tight screws.
  - Cross-threading is specified as a failure mode but is currently
    recorded through the fastener's generic `damaged` flag with a
    thread-damage description; a dedicated cross-threaded state is a
    candidate refinement once the fastener-management spec settles its
    hole/thread bookkeeping.
  - Wrong-bit and over-torque outcomes are fixed-probability rolls (75%
    and 50%). A future version may make them depend on screw size or
    driver pairing; any such change must update Failure modes and the
    torque table together.
  - Loading while loaded is an error in this spec (no silent swap). Any
    implementation that permits overwrite-on-load is out of spec and
    must be aligned, since the unload-then-load cost is a scored part of
    the tool.
- **Compatibility rule.** The five call names and the `BitSpec` /
  `ScrewRef` types are the stable interface. Adding a call, renaming a
  call, or making any management step implicit (auto-load, auto-torque,
  batch driving) is a breaking change to the benchmark's core measurement
  and requires a major version bump of this spec and a note in the
  harness changelog, not a silent edit.
- **Change log discipline.** Future revisions append entries here with:
  what changed, which section, what grounding or simulation evidence
  motivated it, and whether scores from earlier versions remain
  comparable. Marathon results in particular are only comparable across
  versions with identical state-persistence and time-cost rules.
