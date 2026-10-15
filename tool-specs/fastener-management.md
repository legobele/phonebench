# Fastener Management (`fm_`) — Screw Mat and Screw Identity Tracking

> **SIMULATED SYSTEM — DESIGN SPECIFICATION**
>
> This document specifies a subsystem of a **simulated** robotic phone-repair
> arm benchmark. The mat, slots, sensors, screw objects, call set, timings,
> and damage events described here are simulation constructs. They are not a
> description of, and make no claim about, any real-world product, tool, mat,
> robot arm, or repair service. Where phone screw data is cited, it is cited
> only as benchmark grounding drawn from the iFixit guides named
> below, and only for the model those guides cover.
>
> Status: v0.1 draft. Full per-model screw coverage is **PENDING** — see
> Versioning notes.

---

## Purpose

Fastener Management owns **screw identity** for the benchmark.

The screwdriver subsystem (`sd_` calls: `sd_load_bit(bit_spec)`,
`sd_unload_bit()`, `sd_set_torque(level)`, `sd_loosen(screw)`,
`sd_tighten(screw)`) drives screws. It does **not** track them. Once
`sd_loosen` has backed a screw out of its hole, the screwdriver has no
memory of which hole it came from, how long it is, or which phone it
belongs to. Left to the screwdriver alone, every removed screw degenerates
into "a small screw, probably like the others" — and in phone repair that
approximation is the one that destroys the device (see Semantics:
long-screw damage).

This system exists to prevent that degeneration. Its jobs are to:

1. Give **every screw removed from a phone a tracked identity** at the
   moment of removal, and preserve that identity until the screw is
   reinstalled, quarantined, declared lost, or legitimately replaced by
   an exact-spec spare.
2. Provide a **physical (simulated) place for screws to be**: a gridded
   magnetic mat/tray with addressable slots, so that "where is this
   screw?" always has a checkable answer instead of relying on the
   agent's memory.
3. Act as the **identity checkpoint on the way back in**: a screw is only
   handed to `sd_tighten` for a given hole after this system has verified
   that the screw's recorded identity matches that hole's expected spec.
4. Provide the **accounting sign-off** for a job: at end of job, prove
   that every screw that came out is accounted for — reinstalled,
   quarantined, replaced, or formally lost with its consequences
   applied — and that no screw is left over, missing silently, or
   carried into the next phone.
5. Make good organisation **cost something and skipping it cost more**.
   Placing and retrieving screws through the mat takes simulated time
   on every screw. Skipping the mat is permitted (no-mat work mode)
   but replaces certain identity with explicit uncertainty. That
   trade-off — the organisational tax versus the risk it buys down —
   is a scored skill of the benchmark, not an implementation detail.

**Contract with the screwdriver (explicit).** Screw references are
created and owned by this system. The `ScrewRef` values that
`sd_loosen(screw)` and `sd_tighten(screw)` consume are the references
this system issues and resolves:

- Before removal, this system resolves a target hole
  (`phone_id` + `origin_location`) to the expected `ScrewRef` for that
  hole, from the phone's fastener layout.
- On successful `sd_loosen`, this system instantiates the removed screw
  as a tracked object (see the identity record in Physical description)
  and that instance — not a bare description such as "a Y000 screw" —
  is what must be placed, retrieved, and finally passed back to
  `sd_tighten`.
- `sd_tighten` must not be called with a raw, unregistered, or
  pile-sourced screw description where a tracked `ScrewRef` is required.
  Code that addresses fasteners internally as
  `(part_name, fastener_index)` treats that pair as a resolution of
  `origin_location`, never as a substitute identity: two screws can share
  a driver and look identical while differing in length, and
  `(part_name, fastener_index)` only has meaning while the mapping back
  to the tracked instance is intact.

This system does **not**: drive screws, choose torque, decide whether a
repair step is in scope, judge cosmetic condition, or evaluate the
quality gates. It supplies identity, location, and accounting facts to
the systems that do.

---

## Physical description (simulated)

### The mat / tray

The simulated workstation has one screw mat:

- A **gridded magnetic tray**. Magnetism (simulated) holds a placed
  screw in its slot against incidental vibration and arm movement; it
  does not sort, identify, or move screws by itself.
- The grid is **addressable**: every slot has a stable `slot_id` for the
  duration of a job (grid coordinate form, e.g. `M-C04-R03`, plus a
  simulation-unique slot handle). A slot holds **at most one screw**.
- Each slot has simulated occupancy sensing: the simulation knows, and
  `fm_query_slot` reports, whether a slot is `empty`, `occupied` (with
  the `ScrewRef` of its occupant), `reserved` (assigned, not yet
  placed), or `quarantined` (see `fm_quarantine`).
- The mat has a **partition boundary** used in Marathon mode: slots are
  allocated to the currently active phone only, and no allocation for
  phone N+1 exists while phone N is open (see Semantics: Marathon).
- The mat is **not** a pile. There is no "put it somewhere on the mat"
  operation. A screw is either in a named slot via `fm_place`, in the
  arm's gripper in transit, in a hole, quarantined, or lost. Anything
  else is an unrecorded-screw failure (see Failure modes).
- The mat performs **no visual identification**. Slot sensing reports
  occupancy, not screw length or driver type. Identity comes from the
  tracking record created at removal, which is precisely why the record
  must be created at removal and never reconstructed later from
  appearance.

Simulated sensors elsewhere in the workstation (in Harnessed Autonomous
mode, the only checkers available) can classify events such as a drop
(`hd_` handling events) and a torque/seating anomaly during tightening.
Those classifiers are fallible inputs to this system; they are not the
mat, and they do not retroactively create identity (see Semantics:
long-screw damage and no-mat work mode).

### The tracked screw object

Every screw removed from a phone exists, from the step it is removed
until its terminal disposition, as a tracked object with this identity:

| Field | Type | Meaning |
|---|---|---|
| `screw_id` | `ScrewId` (opaque, simulation-unique) | Instance identity. Two screws with identical specs are still two distinct objects with distinct `screw_id`s. Created by this system; never reused, including across phones in Marathon. |
| `phone_id` | `PhoneId` | The phone this screw came out of. Immutable. A screw can never be re-badged to another phone. |
| `origin_location` | `HoleId` | The specific hole the screw came from, addressed as `{part_name, fastener_index}` within `phone_id`, resolvable to a bracket/component and a position on it. Immutable. This — not "a battery-cover screw" — is the return address. |
| `driver_type` | `DriverType` | The driver the screw's head requires, e.g. `Pentalobe P2`, `Tri-point Y000`, `Phillips PH000`, `Standoff`. As recorded from the phone's fastener layout / removal, not guessed from appearance. |
| `size` | `DriverSize` | The nominal driver size component of the spec (e.g. `P2`, `Y000`, `PH000` for the driver types above; for a standoff screw, the standoff designation). Kept as a separate field from `driver_type` because the same driver family occurs in more than one size and a wrong-size bit is a screwdriver problem this record must be able to expose. Where a source states a driver only as e.g. "Phillips", `size` is recorded as `UNSPECIFIED` rather than filled in by guesswork. |
| `length_mm` | `float` (mm) | Screw length as specified for `origin_location`. The single most safety-critical field in the record (see long-screw damage). Recorded from layout/spec at removal; never measured "by eye" afterwards. |
| `removed_at_step` | `int` (job step index) | The simulation step at which `sd_loosen` removed this screw. Gives the ledger its ordering and ties the screw to the disassembly stage that exposed it. |

Derived / state fields carried alongside the identity (not part of the
immutable identity itself): `status` (`in_hole`, `in_transit`,
`on_mat`, `reinstalled`, `quarantined`, `lost_outside_phone`,
`lost_inside_phone`, `replaced_by_spare`), current `slot_id` if any,
`head_condition` (`good`, `worn`, `stripped`, `UNKNOWN`), and
`identity_confidence` (`CERTAIN` for a screw tracked through the mat
without a break in custody, `UNCERTAIN` for any screw whose custody
chain broke — see no-mat work mode).

Screws that are part of the phone but never removed in a job never get
an instance record; they remain layout entries. A **spare** screw gets
its own record on first use, with `phone_id` set to the phone it is
destined for, `origin_location` set to its destination hole,
`removed_at_step = null`, and a `provenance = SPARE` marker (see
Semantics: spare-screw policy).

### Why identity cannot be eyeballed — grounded example

Grounded context, from the iPhone 14 Pro Max repair guides on iFixit
(guides 153006 and 153334 and their shared prerequisite guides; the
same screw sets recur across those guides — see the repo NOTICE):

- A single phone mixes at least **Pentalobe P2, Tri-point Y000,
  Phillips (PH000 / #00 / #000 as variously stated), and standoff**
  screws.
- The battery connector cover alone — one bracket, one removal step
  (step 17) — is held by **8 Tri-point Y000 screws of three different
  lengths: 5 × 1.3 mm, 2 × 1.6 mm, 1 × 1.9 mm**. Same driver, same
  bracket, adjacent holes, lengths differing by 0.3 mm. The guides
  indexed by the slices warn at that step to track each screw and
  return it to its original position, and name a magnetic project mat
  as the tool used there. (The simulated mat in this spec is an
  addressable, sensed abstraction; no capability beyond naming in the
  guide is claimed for any real mat.)
- Elsewhere in the same phone the slices record, among others:
  Pentalobe P2 6.8 mm (bottom edge, ×2); Y000 1.2 mm and 1.5 mm (rear
  camera cover); Phillips 1.4 mm (PH000, front sensor bracket),
  1.5 mm in two head-size variants (loudspeaker), 1.6 mm (earpiece
  speaker), 1.7 mm (rear camera cover), 1.8 mm and 2.3 mm (Taptic
  Engine); and a 2.9 mm standoff screw (Taptic Engine). A full battery
  path totals 17 screws across 9 distinct driver+length specifications.

So within one ordinary job: the same driver drives screws of five or
more lengths; the same length (e.g. 1.5 mm, 1.6 mm) occurs under
different drivers at different brackets; and the dangerous confusions
(1.3 vs 1.6 vs 1.9 mm, all Y000, all from one bracket) are invisible to
any appearance-based check the simulation models. **Identity by eyeball
is impossible, which is the point.** Identity must be carried by this
system's record and the mat's slot discipline, or it does not exist.

> **PENDING:** the consolidated `screw-chart.md` from the index project
> does not yet exist. Until it lands, the table above is illustrative
> grounding from the slices, **not** the benchmark's screw chart. Full
> per-model coverage — every model in the job suite, every hole, its
> expected `driver_type` / `size` / `length_mm`, and its hole-depth
> class for long-screw checks — is PENDING that chart and must be
> imported from it, not hand-extended from this example.

---

## State

Fastener Management maintains, per run:

### Mat occupancy map

```
mat: Map<SlotId, SlotState>

SlotState =
  | { kind: "empty" }
  | { kind: "reserved",  for_screw: ScrewId, phone_id: PhoneId }
  | { kind: "occupied",  screw: ScrewRef,    phone_id: PhoneId }
  | { kind: "quarantined", screw: ScrewRef,  phone_id: PhoneId,
      reason: QuarantineReason }
```

Plus mat-level state: `active_phone_id: PhoneId | null`,
`partition: Set<SlotId>` (slots allocated to the active phone; in
non-Marathon modes this is the whole grid), `mat_generation: int`
(incremented by every `fm_reset_mat`; a `ScrewRef` or `slot_id` from an
older generation is stale and must be rejected), and
`no_mat_mode: bool` for the current job (see Semantics).

### Per-phone ledger

One ledger per phone ever opened in the run, retained after the phone
closes (Marathon accounting depends on old ledgers staying readable):

```
ledger[phone_id]: {
  phone_id: PhoneId,
  job_id: JobId,
  expected: Map<HoleId, ExpectedSpec>,   // from the phone layout:
                                         // {driver_type, size, length_mm,
                                         //  hole_depth_class}
  instances: Map<ScrewId, ScrewRecord>,  // every screw removed, by id
  by_hole: Map<HoleId, ScrewId | SpareId | null>,
                                         // what should / does fill each hole
  removed_count: int,
  reinstalled_count: int,
  open_holes: Set<HoleId>,               // removed, not yet refilled
  sign_off: null | {
    verified_at_step: int,
    result: VerifyResult,
    verified_by_mode: Mode,              // who/what performed the check
  },
  closed: bool,
}
```

The ledger — not the mat — is the durable record. The mat is emptied
between phones; the ledger is not.

### Lost and quarantine lists

```
lost_list: List<{
  screw: ScrewRef,
  declared_at_step: int,
  location_class: "outside_phone" | "inside_phone" | "unknown",
  hd_event_ref: HdEventId | null,        // cross-reference, if a
                                         // handling drop event exists
  resolution: "unresolved" | "recovered" | "replaced_by_exact_spare"
            | "job_failed",
}>

quarantine_list: List<{
  screw: ScrewRef,
  quarantined_at_step: int,
  reason: QuarantineReason,  // "damaged_head" | "wrong_spec_suspect"
                             // | "foreign_phone_suspect"
                             // | "uncertain_identity" | "contaminated"
  slot_id: SlotId | null,    // quarantined screws keep a slot, apart
  disposition: "held" | "discarded_at_signoff" | "cleared_by_review",
}>
```

A screw is in exactly one place in the state model at any time: in its
hole, in transit, in one mat slot (normal or quarantined), on the lost
list, or reinstalled. The state model has no representation for "in a
pile", "somewhere on the bench", or "in the other phone" — attempts to
reach those conditions surface as the failure modes below, not as
states.

---

## Call set

Prefix: `fm_`. Verb-first, like the `sd_` set. All calls are counted by
the simulation and, where stated, cost simulated time (see Time costs).
Types: `ScrewRef` is the opaque tracked-screw handle issued by this
system; `ScrewInfo` is the identity record from Physical description;
`HoleId`, `PhoneId`, `SlotId`, `JobId` are as defined in State.

| Call | Inputs | Outputs | Notes |
|---|---|---|---|
| `fm_expected_screw` | `(phone_id: PhoneId, hole: HoleId)` | `ExpectedSpec \| Error("unknown_hole")` | Read-only. The spec a hole expects: `{driver_type, size, length_mm, hole_depth_class}`. This is what tighten-time checks compare against. |
| `fm_register_removal` | `(phone_id: PhoneId, hole: HoleId, removed_at_step: int)` | `ScrewRef` | Called immediately after a successful `sd_loosen(screw)` for that hole. Creates the tracked instance with its full identity. Until this is called, the removed screw is **unrecorded** (Failure modes). Idempotent per `(phone_id, hole, removal episode)`: a duplicate call returns the existing `ScrewRef` and is logged as a redundant call, it does not mint a second screw. |
| `fm_assign_slot` | `(screw: ScrewRef)` | `slot_id: SlotId \| Error("mat_full") \| Error("wrong_phone_partition") \| Error("stale_generation")` | Reserves the next free slot **in the active phone's partition** for this screw. Reservation is not placement. |
| `fm_place` | `(screw: ScrewRef, slot_id: SlotId)` | `Ack \| Error("slot_occupied") \| Error("slot_not_reserved_for_screw") \| Error("screw_not_in_transit")` | Moves a screw from the gripper into a slot. The normal removal sequence is `sd_loosen` → `fm_register_removal` → `fm_assign_slot` → `fm_place`. |
| `fm_retrieve` | `(slot_id: SlotId, for_hole: HoleId)` | `(screw: ScrewRef, check: IdentityCheck) \| Error("slot_empty") \| Error("slot_quarantined")` | Removes the screw from its slot into the gripper **and runs the identity check for the destination hole** (see Semantics). `IdentityCheck = { result: "match" \| "mismatch" \| "uncertain", expected: ExpectedSpec, actual: ScrewInfo, mismatch_fields: List[str] }`. A `"mismatch"` result is returned, not hidden — what happens next depends on mode (Semantics). |
| `fm_query_slot` | `(slot_id: SlotId)` | `SlotState` | Read-only occupancy query. Reports occupancy and the occupant's `ScrewRef`; does **not** identify an occupant by appearance — an occupant with no record reports as an anomaly, not as a guessed spec. |
| `fm_query_mat` | `(phone_id: PhoneId)` | `List<{slot_id, state, screw: ScrewRef \| null}>` | Read-only. All slots in that phone's partition (or, for a closed phone, the empty partition plus a pointer to its ledger). |
| `fm_screw_info` | `(screw: ScrewRef)` | `ScrewInfo \| Error("unknown_screw")` | Read-only. Full identity + status + `identity_confidence` for a tracked screw. For an untracked/physical-only screw description there is nothing to return: `unknown_screw` is the honest answer, and it is the answer no-mat work keeps getting. |
| `fm_screws_for_phone` | `(phone_id: PhoneId)` | `List<ScrewInfo>` | Read-only ledger view: every instance for the phone, with status. |
| `fm_verify_all_accounted` | `(phone_id: PhoneId)` | `VerifyResult` | The accounting check (Semantics). `VerifyResult = { accounted: bool, reinstalled: int, on_mat: List<ScrewRef>, in_transit: List<ScrewRef>, quarantined: List<ScrewRef>, lost: List<ScrewRef>, open_holes: List<HoleId>, foreign_screws_present: List<ScrewRef>, detail: List[str] }`. `accounted = true` only if every removed screw has a terminal or explicitly-held disposition, no hole that must be filled is open, and no foreign screw is present. |
| `fm_mark_lost` | `(screw: ScrewRef, location_class: "outside_phone" \| "inside_phone" \| "unknown", hd_event_ref: HdEventId \| null)` | `Ack \| Error("already_terminal")` | Declares a screw lost (Semantics: lost screws). Normally follows an `hd_` drop event; the `hd_event_ref` cross-references it. A screw merely not yet placed is not lost — declaring it lost to avoid searching is a scored misuse. |
| `fm_quarantine` | `(screw: ScrewRef, reason: QuarantineReason)` | `slot_id: SlotId \| Error("no_quarantine_slot")` | Moves a screw to a quarantine slot: damaged head, suspect spec, suspect foreign origin, or uncertain identity. A quarantined screw **cannot** be passed to `sd_tighten` (`fm_retrieve` from its slot errors) until cleared. |
| `fm_clear_quarantine` | `(screw: ScrewRef, cleared_by: "technician" \| "classifier_recheck")` | `Ack \| Error("not_quarantined") \| Error("clearance_not_permitted_in_mode")` | Returns a quarantined screw to normal status. In Harnessed Autonomous mode only `classifier_recheck` is available, and it cannot clear `foreign_phone_suspect` or `uncertain_identity` (Semantics: modes). |
| `fm_assign_spare` | `(phone_id: PhoneId, hole: HoleId, spare_spec: ExpectedSpec)` | `(screw: ScrewRef, check: IdentityCheck) \| Error("no_exact_spare") \| Error("spares_not_allowed")` | Draws a spare for a hole whose original is lost/quarantined (Semantics: spare policy). Succeeds only on an **exact** spec match. The returned `ScrewRef` (with `provenance = SPARE`) is what `sd_tighten` consumes. |
| `fm_begin_phone` | `(phone_id: PhoneId, job_id: JobId)` | `Ack \| Error("previous_phone_not_closed") \| Error("mat_not_reset")` | Opens the ledger and partition for a phone. In Marathon, refuses if the previous phone is unclosed or the mat was not reset. |
| `fm_reset_mat` | `(expected_empty_for: PhoneId)` | `Ack \| Error("mat_not_empty", occupants: List<ScrewRef>)` | Verifies every non-quarantine slot is empty, clears reservations, bumps `mat_generation`, clears the partition. **It does not silently discard occupants**: any screw still on the mat is an error naming it, not rubbish to be swept away. |
| `fm_close_phone` | `(phone_id: PhoneId)` | `Ack \| Error("not_accounted") \| Error("loose_screw_inside")` | Job sign-off for fasteners. Requires a passing `fm_verify_all_accounted` for this phone in this generation. In Marathon this is a **required step** before `fm_begin_phone` for the next phone. |
| `fm_set_no_mat_mode` | `(job_id: JobId, enabled: bool)` | `Ack` | Declares no-mat work for a job (Semantics). The declaration is logged and scored; working without the mat *without* declaring it is detected as unrecorded screws, which is worse. |

Errors are values, not exceptions that abort the job: the simulation
records the error, charges the call's time, and lets the agent recover —
recovery quality is part of the score.

---

## Semantics

### The normal custody chain

For each screw, the intended chain is unbroken:

```
in_hole
  -- sd_loosen + fm_register_removal --> in_transit (gripper)
  -- fm_assign_slot + fm_place -------> on_mat (named slot)
  -- fm_retrieve(for_hole) ------------> in_transit, identity-checked
  -- sd_tighten -----------------------> reinstalled
```

Any break in the chain — a removal with no registration, a placement
with no slot, a retrieval for the wrong hole, a tightening with no
retrieval — degrades that screw's `identity_confidence` to `UNCERTAIN`
or triggers a named failure mode. Identity in this system *is* the
custody chain; there is no other source for it.

### LONG-SCREW DAMAGE — the signature failure

**Definition.** Long-screw damage is the classic phone-killer this
benchmark is built around:

> A screw whose `length_mm` is **greater than the length specified for
> the hole it is driven into**, where that hole's depth is shallower
> than the screw is long, so that on tightening the screw's tip pierces,
> cracks, or stress-loads the board (or another component) beneath the
> hole.

In the simulation this is a **catastrophic damage event**: it appends
to the phone's damage log at the moment of the offending `sd_tighten`,
and its modelled consequence is a board-level failure — prototypically
the phone **no longer powers on**. It therefore fails every quality
tier (see Interactions with the quality gates) regardless of how fast
or otherwise clean the job was. It is the benchmark's **signature
accuracy failure**: not a fumble, but an information failure — the
agent had, or could have had, a record that would have prevented it.

The grounded example shows why it is easy: on one bracket, 1.3 mm,
1.6 mm, and 1.9 mm Y000 screws sit in adjacent holes. Putting the
single 1.9 mm screw into a 1.3 mm hole, or a 1.6 mm screw into a
1.3 mm hole, requires no carelessness of hand at all — only the loss
of which screw was which. Fractions of a millimetre, no visual
difference the simulation credits, total consequence.

Related but distinct events, **not** long-screw damage: a too-*short*
screw in a hole (under-retention: the bracket is not properly secured,
the fastener fails verification / counts as not seated — an incomplete
repair, not board damage); a wrong-*driver* screw forced with a
mismatched bit (head damage / cam-out risk, owned jointly with the
screwdriver spec); and over-torque at correct length (screwdriver
torque domain). Only the long-screw-in-shallow-hole event carries the
catastrophic board-damage consequence.

**Prevention and detection — in order of where they act:**

1. **Prevention by custody (the mat).** If every screw is registered,
   slotted, and retrieved by identity, a long screw is never in the
   gripper for a shallow hole in the first place. This is the primary
   defence and the reason the organisational tax exists.
2. **Identity check at `fm_retrieve`.** `fm_retrieve(slot_id, for_hole)`
   compares the occupant's recorded `driver_type`, `size`, and
   `length_mm` against `fm_expected_screw(phone_id, for_hole)`.
   A length (or driver/size) mismatch returns
   `IdentityCheck.result = "mismatch"` with the differing fields named,
   *before* any driving happens. In Harnessed Semi-Auto and Manual
   modes a mismatch is a **hard stop**: the simulation refuses the
   subsequent `sd_tighten` of that screw into that hole until the agent
   retrieves a matching screw or a technician overrides (Manual) with
   the override logged. In Harnessed Autonomous mode there is no human
   to stop the agent, so the mismatch is returned as a prominent
   result the agent must act on; an agent that proceeds anyway has
   made a scored, logged decision to ignore a certain warning.
3. **Identity check at `sd_tighten` time (backstop).** Independently of
   retrieval, the tightening path re-resolves the `ScrewRef` being
   driven against the destination hole's expected spec. If the screw
   was never retrieved through `fm_` (pile work, a stale-generation
   reference, a hand-constructed description), this check runs on
   whatever identity is available: a tracked screw with a mismatched
   length is blocked in Semi-Auto/Manual and flagged-and-logged in
   Autonomous, exactly as at retrieval; an **untracked** screw has no
   length on record, so the check returns `"uncertain"` — see no-mat
   work mode for what that means per mode.
4. **Sensor classification during driving (Autonomous last resort).** In
   Harnessed Autonomous mode, sensor classifiers are the only in-the-
   moment checkers. The relevant classifier watches **torque against
   seating depth** during `sd_tighten`: a screw that should seat at its
   spec depth but instead meets rising resistance *before* seating
   (tip contact with the board) produces a **torque-anomaly-at-depth**
   classification. If the agent (or the harness's reflex rule, where
   configured) aborts the drive on that classification before full
   torque, the event is recorded as a **near-miss**: the screw is
   wrong, it is quarantined as `wrong_spec_suspect`, and no board
   damage is logged — *provided* the abort came before the simulated
   pierce threshold. Past that threshold, the classification is merely
   the damage event's witness. Classifiers are probabilistic in the
   simulation: they can miss the anomaly (false negative → damage) and
   can fire on a correct screw (false positive → the agent must
   re-verify identity, costing time, not the job). A classifier catch
   is a save, never a strategy: an agent whose *plan* is "drive it and
   see if the torque complains" accumulates near-misses and false-
   positive re-checks and is scored accordingly.
5. **Post-hoc detection.** If a long screw was fully driven, later
   verification (power-on failure, board-damage entry in the damage
   log) exposes it at gate evaluation. There is no repair action for it
   within the job: backing the screw out does not un-pierce the board.
   The damage entry stands.

### No-mat work mode (the unorganised pile)

An agent may work without the mat: screws are removed and kept as an
unorganised pile (physically: gripper-to-bench, no slots), then picked
from the pile for reassembly.

- This mode is entered per job via `fm_set_no_mat_mode`, or entered
  *de facto* by any removal that is never registered/placed.
- In this mode, **screw identity is uncertain by construction**. A
  pile screw has a physical existence but no trustworthy record:
  `fm_screw_info` on it returns `unknown_screw` (or, if it was
  registered but never slotted, a record with
  `identity_confidence = UNCERTAIN` once it has been mixed with others).
  Lengths cannot be re-derived from appearance (see Physical
  description), and the simulation does not permit the agent to
  "measure" pile screws back to certainty with workstation sensors in
  Autonomous mode; a technician in Manual mode may measure and
  re-certify individual screws, at technician-review time cost, which
  is just the organisational tax paid late and at a worse rate.
- Consequently every pile-sourced `sd_tighten` runs its tighten-time
  check as `"uncertain"`. In Semi-Auto and Manual modes, `"uncertain"`
  is treated like `"mismatch"` for long-screw purposes: blocked until
  the screw is identified or replaced. In Autonomous mode the agent
  may proceed, and each such drive is a gamble the simulation resolves
  against ground truth: a pile pick that happens to be the correct
  screw succeeds silently; a pick that is over-length for the hole is
  long-screw damage, with **no** identity warning having been available
  to ignore — the agent traded the warning away when it skipped the mat.
- No-mat mode does not exempt the job from accounting:
  `fm_verify_all_accounted` still runs, and pile screws that cannot be
  tied to holes make `accounted = false` until every hole is filled
  with a verified screw and every surplus pile screw is quarantined
  and explained.
- Skipping the mat is therefore a legible strategy with a priced risk,
  not a loophole: it saves the per-screw place/retrieve time (Time
  costs) and buys exposure to the benchmark's worst failure on every
  mixed-length bracket.

### Lost screws

A screw is **lost** when custody ends involuntarily: typically an
`hd_` handling drop event (`hd_` drop events are owned by the handling
spec; this system only consumes and cross-references them), a fumbled
transfer, or a screw that leaves the gripper/mat and cannot be
recovered by a search action.

- `fm_mark_lost(screw, location_class, hd_event_ref)` records the loss
  on the lost list, frees any slot the screw was associated with, and
  marks its hole in the ledger as open-with-cause. The
  `location_class` is load-bearing and must be declared honestly from
  the event evidence; `unknown` is permitted but is treated as
  `inside_phone` for job-closure purposes until resolved, because the
  safe assumption about an unlocated screw near an open phone is that
  it may be in the phone.
- **Lost outside the phone.** The hole it came from is unfilled. The
  consequences are determined at accounting:
  - **Missing screw = incomplete repair, by default.** A bracket or
    component left short of a screw it had at entry is not properly
    re-fastened, so `fm_verify_all_accounted` returns
    `accounted = false` and the job's repair-complete condition is not
    met — the job fails even the Normal gate — **unless** the job
    explicitly declares that fastener optional
    (`job.allow_missing_fasteners` naming the hole) **or** the hole is
    refilled by an exact spare under the spare policy below.
    A job-level allowance is a property of the job spec, never
    something the agent may assert after the fact.
  - The lost screw itself, outside the phone, does no further damage;
    it is a completeness and accounting problem, not a safety one.
- **Lost inside the phone.** Qualitatively worse. A loose screw inside
  a closed phone is a **rattle and short-circuit risk** and a foreign
  object against the board. Rules:
  - The job **cannot close** while a `lost_inside_phone` (or
    unresolved `unknown`) entry exists: `fm_close_phone` returns
    `Error("loose_screw_inside")`.
  - The loss must be **resolved**: the screw is recovered (it re-enters
    custody via registration of the recovery, returns to the mat or its
    hole, and the lost entry's resolution becomes `recovered`), or the
    phone is re-opened and searched until the simulation confirms the
    interior is clear. There is no "probably fine" disposition.
  - If the job is force-closed or submitted with the loose screw
    unresolved, **the job fails** — the unresolved interior foreign
    object is a damage-risk disqualifier at gate evaluation (see
    Interactions), independent of whether the modelled short has
    "happened yet".
  - Substituting a spare into the empty hole does **not** resolve a
    lost-inside entry. The hole and the loose screw are two separate
    problems; fixing one leaves the other.
- A screw dropped and immediately recovered in the same handling event
  (per the `hd_` event's outcome) is not lost: custody is annotated,
  `identity_confidence` is preserved if the screw never mixed with
  others, and no `fm_mark_lost` is needed. `fm_mark_lost` is for
  unrecovered screws only.

### Spare-screw policy

- **Spares exist**, in a simulated spare stock indexed by exact spec
  `{driver_type, size, length_mm}` (plus head variant where the layout
  distinguishes one — e.g. the two 1.5 mm Phillips head sizes in the
  grounded example are different spares).
- **A spare of the wrong length is not a spare.** Neither is a spare of
  the right length and wrong driver, or the right driver and wrong
  head. `fm_assign_spare` matches on the full expected spec of the
  destination hole and returns `Error("no_exact_spare")` rather than
  the nearest available screw. There is no call in this system that
  returns an approximate fastener, deliberately: "close enough" is the
  long-screw failure wearing a helpful expression.
- A successfully assigned spare is a first-class tracked screw
  (`provenance = SPARE`, its own `screw_id`), goes through the same
  retrieve/tighten identity checks (which it passes by construction),
  and is recorded in the ledger against its hole, with the original
  screw's lost/quarantine entry cross-linked to it
  (`resolution = "replaced_by_exact_spare"`).
- Whether spares may be used at all is a **job/mode property**:
  `job.allow_spare_substitution` (default: allowed for Normal-tier
  jobs, and allowed in all modes, but in **Manual mode a spare
  substitution requires technician approval**, recorded on the ledger;
  in **Harnessed Semi-Auto** the substitution is surfaced for review
  before `sd_tighten`). If spares are not allowed for a job, a lost
  screw's hole stays open and the completeness consequence above
  applies.
- A spare restores **completeness**, not history: the lost entry
  remains on the ledger permanently, and gate interaction is as defined
  in Interactions with the quality gates.

### Quarantine

Quarantine is the holding state for a screw that exists but must not
be used: a stripped or worn head, a screw whose spec is suspect (e.g.
the wrong screw caught at retrieve, or the survivor of a torque-
anomaly near-miss), a screw suspected of belonging to a different
phone, or any screw whose identity has become uncertain.

- Quarantined screws keep a mat slot, visibly segregated in state as
  `quarantined`; they still count in `fm_verify_all_accounted` (as
  held, not missing).
- A quarantined screw cannot be retrieved for a hole. It leaves
  quarantine only via `fm_clear_quarantine` (with the mode restrictions
  in the Call set) or by remaining quarantined at sign-off, in which
  case its hole needs a spare or an allowance, exactly as for a loss.
- Quarantine is cheap and reversible; driving a suspect screw is
  neither. The scoring model treats a needless quarantine as a small
  time/efficiency cost and a skipped necessary quarantine as an
  accuracy risk.

### Modes

The same state and calls apply in all modes; what changes is **who or
what checks, and what a failed check does**:

| | Harnessed Autonomous | Harnessed Semi-Auto | Manual | Harnessed Marathon |
|---|---|---|---|---|
| Checker | Sensor classifiers + this system's checks only; no human | System checks + harness review prompts | A human technician, guided by the model; technician reviews identity decisions | As Autonomous, plus Marathon accounting rules below |
| `fm_retrieve` mismatch | Returned and logged; agent may override at scored risk | **Hard stop** on the mismatched tighten | **Hard stop**; technician may override, logged with technician identity | As Autonomous |
| Tighten-time `"uncertain"` (pile/untracked) | Agent may proceed; resolved against ground truth | Blocked until identified | Blocked until technician identifies/measures | As Autonomous |
| Torque-anomaly classification | May abort the drive (near-miss) if acted on before pierce threshold | Surfaced; drive paused for review | Surfaced to technician | As Autonomous |
| Spare substitution | Allowed if job allows | Surfaced for review before tightening | Technician approval required | As Autonomous, and spares are drawn per-phone — a spare assigned to phone N is an instance of phone N's ledger |
| `fm_clear_quarantine` | `classifier_recheck` only; cannot clear foreign/uncertain | Review may clear | Technician may clear any reason | As Autonomous |

In Manual mode this system is the model's instrument panel for the
technician: the model proposes (`fm_screw_info`, `fm_query_mat`,
`IdentityCheck` results) and the technician disposes, and every
technician disposition is recorded against the ledger so the job's
accounting is as auditable as an autonomous one.

### Marathon specifics

Harnessed Marathon runs a **queue of phones** through one workstation
and one mat. Its defining disaster is **cross-phone contamination**:
a screw from phone N migrating into phone N+1.

- **Per-phone partitioning.** `fm_begin_phone` allocates the mat
  partition to the active phone only. `fm_assign_slot` for a screw
  whose `phone_id` is not the active phone errors
  (`wrong_phone_partition`). There is no moment at which two phones'
  screws legitimately share the mat.
- **Mat reset between phones.** The sequence between phones is fixed:
  `fm_verify_all_accounted(phone N)` → `fm_close_phone(phone N)` →
  `fm_reset_mat` → `fm_begin_phone(phone N+1)`. `fm_reset_mat` verifies
  emptiness rather than assuming it; any occupant at reset is an error
  naming the screw, and the marathon does not advance until the
  occupant is dispositioned (reinstalled into its still-open phone,
  quarantined into the ledger's care, or marked lost with consequences).
- **Sign-off is a required step.** `fm_verify_all_accounted` +
  `fm_close_phone` are not optional end-of-job hygiene in Marathon:
  `fm_begin_phone` for the next phone refuses
  (`previous_phone_not_closed` / `mat_not_reset`) without them. An
  agent cannot trade the sign-off away for queue speed.
- **Cross-phone migration is a defined catastrophe.** If a screw whose
  `phone_id = N` is tightened (or attempted, in Semi-Auto/Manual
  terms: presented) into a hole of phone N+1:
  - The identity checks catch it on two independent fields —
    `phone_id` mismatch is a mismatch even if `driver_type`, `size`,
    and `length_mm` all coincidentally match, because screws of the
    same spec occur in every phone. Spec equality is not identity.
  - If driven, the event is recorded against **both** phones: phone
    N+1 has a foreign screw installed (and, if the foreign screw is
    over-length for its hole, long-screw damage on top), and phone N —
    if its ledger was closed over the discrepancy — has a falsified
    accounting, which reopens its sign-off as failed.
  - If the migration is discovered before driving (a foreign screw
    found in the active partition, e.g. by `fm_query_mat` or a failed
    reset), the screw is quarantined as `foreign_phone_suspect`; in
    Autonomous mode that quarantine cannot be cleared by classifier
    recheck, because no classifier can prove a negative about which
    phone a loose screw came from.
  - Net effect: one migrated screw can fail two jobs in the queue.
    That asymmetry is intentional and is why Marathon scoring weights
    reset discipline so heavily.

### Verification semantics (`fm_verify_all_accounted`)

The check is purely accounting; it does not re-drive or re-measure
anything. It passes (`accounted = true`) iff, for the given phone:

1. Every instance in the ledger is in a terminal or held disposition:
   `reinstalled`, `quarantined` (held), `lost` with a completed lost
   entry, or `replaced_by_spare` (for the original, with the spare
   itself `reinstalled`).
2. No screw is `in_transit` or `on_mat` — nothing is left in the
   gripper or on the mat at sign-off.
3. Every hole in `open_holes` is covered by an explicit job allowance
   (`allow_missing_fasteners` or `allow_spare_substitution` already
   exercised); an unexplained open hole fails the check.
4. No `lost_inside_phone` / unresolved-`unknown` lost entries exist
   (these also separately block `fm_close_phone`).
5. No foreign screws: every screw on the mat, in quarantine, or
   installed in this phone carries this phone's `phone_id`.

The returned `VerifyResult` always enumerates the offenders, so a
failed verification is a worklist, not a bare "no".

---

## Time costs

All times are **simulated seconds**, charged to the job clock. They are
benchmark tuning parameters, not measurements of any real process.

| Action | Cost (sim s) | Notes |
|---|---|---|
| `fm_expected_screw` | 0.5 | Read-only lookup. |
| `fm_register_removal` | 1.0 | Per screw, at removal. |
| `fm_assign_slot` | 0.5 | Reservation only. |
| `fm_place` | 2.0 | Gripper-to-slot placement, per screw. |
| `fm_retrieve` (incl. identity check) | 2.0 | Per screw. The check itself is free within this cost — verification is not where the tax sits. |
| `fm_query_slot` / `fm_screw_info` | 0.5 | Per call. |
| `fm_query_mat` / `fm_screws_for_phone` | 1.0 | Per call. |
| `fm_quarantine` | 2.0 | Placement into a quarantine slot. |
| `fm_clear_quarantine` | 1.0 | Plus, in Manual mode, technician-review latency as modelled by the harness. |
| `fm_assign_spare` | 3.0 | Stock lookup, spec match, ledger cross-linking. |
| `fm_mark_lost` | 1.0 | Declaration only; any search for the screw is a handling (`hd_`) cost, charged there. |
| `fm_verify_all_accounted` | 5.0 | Per invocation. Re-running it repeatedly to "check if it passes yet" is charged every time. |
| `fm_reset_mat` | 10.0 | Marathon / between-jobs: emptiness verification, reservation clear, generation bump. |
| `fm_begin_phone` / `fm_close_phone` | 2.0 each | Ledger open / sign-off. |
| `fm_set_no_mat_mode` | 0.0 | The saving is in the skipped per-screw costs, not here. |

**The organisational tax, stated plainly.** The full mat path costs
**5.5 sim s per screw** (register 1.0 + assign 0.5 + place 2.0 +
retrieve 2.0), plus fixed per-job costs. On the grounded 17-screw
battery path that is ~94 sim s of pure fastener organisation — time a
sloppy agent can appear to save entirely by working from a pile. That
is the trap the benchmark sets: the tax is certain, visible, and
charged on every job; the catastrophe it prevents is probabilistic
per screw and total when it lands. Scoring (time, efficiency,
accuracy) is calibrated so that skipping the tax is a bet, not a
dominant strategy — and on any bracket with mixed lengths, it is a
bet against the signature failure.

No-mat mode charges none of the per-screw mat costs. It charges
instead: `UNCERTAIN` identity on every pile screw, blocked tightens in
Semi-Auto/Manual, technician measuring time in Manual, and the
expected cost of long-screw damage in Autonomous — which is not a
time cost at all, but a failed job.

---

## Failure modes

Each failure mode is a named, logged, scored event in the simulation.

| Failure mode | Definition | Detection | Immediate consequence |
|---|---|---|---|
| **Wrong-screw-in-hole** | A tracked screw is driven into a hole whose expected spec it does not match — wrong `length_mm` (see long-screw damage if over-length), wrong `driver_type`/`size`, or right spec but wrong instance where the job requires original-instance return, or a foreign phone's screw. | Identity check at `fm_retrieve`; backstop check at `sd_tighten`; torque-anomaly classification during the drive. | Over-length into a shallow hole: catastrophic damage event. Otherwise: fastener fails verification (not correctly seated / wrong spec) → incomplete repair; hard stop in Semi-Auto/Manual if caught pre-drive. |
| **Unrecorded screw** | A screw is removed via `sd_loosen` with no `fm_register_removal`, so it exists physically with no identity. The root failure behind most pile disasters. | Simulation custody audit: a physical screw with no instance record; also surfaced when it is later presented to `sd_tighten` (tighten-time check returns `"uncertain"` / `unknown_screw`). | `identity_confidence` can never be retroactively made `CERTAIN` for this screw in Autonomous mode; it must be quarantined as `uncertain_identity`, measured and re-certified by a technician in Manual mode, or the hole it eventually fills must be spare-filled and this screw quarantined. |
| **Double-slotting** | Two screws assigned/placed to one `slot_id`, or one screw recorded in two slots. Physically: the second placement displaces or stacks on the first; in state terms the occupancy map is violated. | `fm_place` returns `slot_occupied`; `fm_assign_slot` never returns an occupied/reserved slot. The failure only occurs if an agent forces past errors or works off-mat and reconstructs slots from memory. | The displaced screw's custody is broken → its identity degrades to `UNCERTAIN`; both screws must be re-verified (Manual: technician; Autonomous: quarantine both and spare-fill their holes) before either may be tightened. |
| **Mat not reset** | A new phone is begun with occupants, reservations, or a stale generation left from the previous phone. | `fm_begin_phone` errors (`mat_not_reset`, `previous_phone_not_closed`); `fm_reset_mat` errors naming occupants. | Marathon does not advance. If somehow bypassed, every subsequent identity check operates on a contaminated partition — treated by scoring as the agent having chosen contamination, and any resulting cross-phone event is scored as migration, below. |
| **Cross-phone screw migration** | A screw with `phone_id = N` is placed, retrieved for, or driven into phone N+1. Marathon-specific (in single-job modes the same event is wrong-screw-in-hole / foreign screw). | `phone_id` check in `fm_assign_slot` (partition), `fm_retrieve`, and the tighten-time backstop; `fm_reset_mat` occupant errors; `fm_verify_all_accounted` foreign-screw check on both phones. | Defined catastrophe (Semantics: Marathon): fails the receiving job; reopens and fails the donor job's sign-off if it was closed; the screw is quarantined as `foreign_phone_suspect` and cannot be classifier-cleared in Autonomous mode. |
| **Lost screw** | Custody ends involuntarily; screw unrecovered (see Semantics: lost screws for the outside/inside distinction). | `hd_` drop event cross-reference; custody audit at `fm_verify_all_accounted`. | Outside: hole open → incomplete repair unless job allowance or exact spare. Inside: job cannot close; unresolved at submission → job fails. |
| **Spare misuse** | Any use of a non-exact screw as a "spare": wrong length (long or short), wrong driver/size/head, a spare drawn for the wrong hole, a spare used without a lost/quarantined original to justify it, or a spare substitution made without required approval (Manual) / review (Semi-Auto). | `fm_assign_spare` exact-match (refuses non-exact outright); ledger audit (spare with no corresponding lost/quarantine entry); tighten-time identity check. | A wrong-length "spare" driven anyway is not a lesser offence — it *is* wrong-screw-in-hole, with long-screw damage if over-length. An unjustified spare leaves the original unaccounted, failing `fm_verify_all_accounted`. |
| **Quarantine abuse / neglect** | Neglect: a suspect screw is driven instead of quarantined. Abuse: quarantine (or `fm_mark_lost`) used to sideline a screw the agent merely cannot be bothered to place or find. | Tighten-time checks and damage/near-miss records (neglect); ledger patterns and mode review (abuse). | Neglect inherits the consequence of whatever the screw does in the hole. Abuse leaves a hole to be spare-filled, consumes spares and verification time, and is scored as an efficiency/accuracy fault even when the job still passes. |
| **Stale-reference use** | A `ScrewRef` or `slot_id` from before an `fm_reset_mat` (older `mat_generation`), or for a closed phone, is used for a current operation. | Generation check on every mutating call (`stale_generation`). | Call errors; if the stale reference was an attempt to retrieve a previous phone's screw for the current phone, it is additionally logged as an attempted migration. |

---

## Interactions with the quality gates

Quality gates are **absolute** and are judged against the phone's
**entry condition**: pre-existing damage, wear, and state recorded at
intake are never the agent's fault — and never its cover. Fastener
Management does not evaluate the gates, but the facts it owns decide
several of them. Tier definitions as used here: **Normal** = the phone
powers on, the repair is complete, and there is no damage; **High** =
Normal, plus any damage or wear disqualifies and user data must be
untouched; **Max** = High, plus an invisibility standard (the repair
leaves no trace that it happened, beyond the intended fix itself).

- **Long-screw damage fails every tier.** It is a damage-log entry
  (fails Normal's no-damage condition), its prototypical consequence is
  no-power-on (independently fails Normal), and a fortiori it fails
  High and Max. There is no tier at which a fast or otherwise elegant
  job survives it, and no time or efficiency score compensates: gates
  are absolute.
- **Incomplete fastening fails Normal, hence all tiers.** A hole left
  open by a lost screw (no job allowance, no exact spare), a fastener
  left unseated or under-torqued after a wrong-screw event, or any
  part not properly re-fastened means the repair is not complete.
  `fm_verify_all_accounted` failing is the fastener-level expression
  of exactly this.
- **An unresolved screw lost inside the phone fails the job at every
  tier**, as an unresolved damage/short risk recorded against the
  phone, even if the phone currently powers on: the gate judges the
  condition the phone is left in, not only failures already observed.
- **Damage and wear from fastener handling is judged vs entry.** A
  screw head stripped during the job, a bracket stressed by a wrong
  screw that was caught before board damage, a near-miss torque event
  that marked a hole — none of these exist at entry, so all of them
  count. At **Normal**, only actual damage counts (a stripped head that
  still seats and verifies may pass Normal, while failing the repair's
  own fastener verification if it cannot be correctly seated). At
  **High**, *any* such new wear — including a stripped or marked head
  on an otherwise functional screw — disqualifies. At **Max**, the
  invisibility standard additionally disqualifies any visible trace of
  the fastener work: substituted screws that are not indistinguishable
  in spec and finish from the originals, re-certified pile screws with
  handling marks, or a ledger-visible intervention where the delivered
  phone shows it.
- **Exact spare substitution, correctly done, is gate-neutral at
  Normal and High** — provided the job allows spares, the required
  mode approval/review happened, the original loss caused no damage or
  wear, and no screw remains lost inside the phone: the repair is
  complete, undamaged, and user data is untouched. At **Max**, a spare
  passes only if it is indistinguishable from the original it replaces
  (exact spec *and* no visible difference); a spec-exact but visibly
  different spare is an invisibility failure. A spare substitution
  cannot launder a loss: the lost entry stays on the ledger, and if
  the "lost" screw is later found inside the phone, the loose-screw
  rule applies retroactively to the closed job's evaluation.
- **Cross-phone migration in Marathon fails both affected jobs** at
  gate level: the receiving phone has a foreign fastener (incomplete/
  incorrect repair; plus damage if over-length), and the donor phone's
  accounting was false (a screw signed off as reinstalled/held was in
  fact exported), which voids its completeness.
- **What Fastener Management does *not* do to gates:** correctly
  tracked, correctly reinstalled original screws are invisible to gate
  evaluation — as they should be. The mat's time costs affect time and
  efficiency *scores*, never gate outcomes. Organisation is how a job
  stays passable; it is never itself a gate condition, except where
  Marathon makes `fm_verify_all_accounted` + `fm_close_phone` a
  required procedural step for advancing the queue.

---

## Versioning notes

- **This spec:** v0.1 — first design draft of the `fm_` subsystem.
  Call names, the identity record, time costs, and check placement
  (retrieve-time, tighten-time, classifier) are the stable surface;
  numeric time costs and classifier behaviour (false-positive /
  false-negative rates, pierce-threshold placement) are tuning
  parameters expected to change under benchmark calibration without a
  spec-major change.
- **Screw data dependency — PENDING.** Per-model screw charts are
  **not** finalised in this version. A consolidated screw chart for
  the iPhone 14 Pro Max (from iFixit guides 153006 and 153334; see
  the repo NOTICE) is still pending; the grounded example in
  Physical description is drawn from those guides for that one model
  and must not be generalised to other models in the job suite. When
  the consolidated chart lands, this
  spec requires a data update, not a design change: import per-hole
  `driver_type`, `size`, `length_mm`, and hole-depth class for every
  model, and re-check the failure-mode examples against it. Until
  then, any model other than the grounded example runs on placeholder
  layout data and results on it should be read accordingly.
- **Cross-spec dependencies.** `sd_loosen` / `sd_tighten` signatures
  and the tightening-path backstop check are co-owned with the
  screwdriver spec; `hd_` drop-event shape (event id, outcome,
  location evidence) is owned by the handling spec and consumed here
  only as `hd_event_ref` + `location_class`; job flags
  (`allow_missing_fasteners`, `allow_spare_substitution`) are owned by
  the job spec. Changes to any of those require a consistency pass
  over Semantics and the Call set.
- **Identity record versioning.** The identity field list
  (`screw_id`, `phone_id`, `origin_location`, `driver_type`, `size`,
  `length_mm`, `removed_at_step`) is versioned as identity-schema v1.
  Adding derived/state fields (status, confidence, provenance) does
  not bump the identity schema; adding, removing, or redefining an
  identity field does, and invalidates comparisons against ledgers
  written under the older schema.
- **Known open questions for the next revision:** (1) whether
  Harnessed Semi-Auto's hard stop should also apply to a *short*-screw
  mismatch or only over-length and driver mismatches; (2) classifier
  near-miss semantics when the abort happens exactly at the pierce
  threshold; (3) whether Marathon should permit a shared quarantine
  area across the partition boundary (currently: no); (4) spare-stock
  finiteness — whether `no_exact_spare` may occur because stock ran
  out, or only because the spec does not exist.
