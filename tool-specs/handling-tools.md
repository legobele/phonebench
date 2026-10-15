# Handling Tools — Design Specification

> **SIMULATED SYSTEM — DESIGN SPECIFICATION ONLY**
> This document specifies tools for a *simulated* robotic phone-repair arm benchmark. All hardware, forces, materials, timings, probabilities, and effects described here are simulation abstractions invented for scoring and evaluation. Nothing in this file is a claim about any real-world product, robot, tool, material property, or repair procedure, and it must not be used as guidance for real device repair.

| Field | Value |
|---|---|
| Spec ID | `handling-tools` |
| Tool prefix | `hd_` |
| Version | 0.1.0 (see Versioning notes) |
| Scope | Everything that picks up, holds, moves, rotates, flips, and places parts and the phone itself |
| Related specs | Cleaning tools (`cl_` prefix) — cross-referenced for smudge remediation and contamination; all other tool specs reference this file for any pick / hold / place action |
| Modes covered | Harnessed Autonomous, Harnessed Semi-Auto, Manual, Harnessed Marathon |

---

## Purpose

Handling tools are the foundation layer of the benchmark. Almost every other operation — opening, fastening, disconnecting, cleaning, testing, closing — requires a part or the phone itself to be held, moved, or repositioned first. This spec defines:

1. The **gripper** (the arm's own end-effector) and **tweezers** (a distinct tool held *by* the gripper) as the two handling instruments.
2. A typed `hd_` call set for gripping, releasing, moving, rotating, flipping, and tweezer operations.
3. The grip-force, orientation, drop-risk, and ESD-style risk models that make handling non-trivial.
4. The **fingerprint / smudge model**: the mechanism by which handling alone — even handling that completes the repair correctly — can fail a job at the quality gates, most severely at Max.

Design intent: handling must never be a free, invisible action. Every contact has a cost in time, a risk profile set by force and speed, and a trace on the device's surfaces. An agent that repairs perfectly but handles carelessly should pass Normal, possibly fail High, and reliably fail Max. An agent that plans its grips (edges only, designated pads, cleaning pass scheduled after handling) should be able to hold Max across a job — and, in Marathon mode, across a queue.

Out of scope: cutting, prying, fastening, heating, cleaning chemistry, and test procedures. Those belong to their own tool specs. If another tool needs to hold something while it works, it does so *through* the state defined here.

---

## Physical description (simulated)

### The gripper — the arm's own end-effector

The simulated arm terminates in a single two-jaw parallel gripper. It is not a separate tool the arm picks up; it is always present and is the default handling instrument.

Simulated properties:

- **Jaws:** Two opposing jaws, each with a replaceable simulated contact pad on its inner face. Default pad is a soft, compliant pad (abstract material, no real-world counterpart claimed). Pads are the *only* part of the gripper intended to touch a held object.
- **Grip aperture:** Abstract range sufficient for (a) a whole phone held by its frame edges, (b) sub-assemblies such as a display assembly or battery, and (c) brackets, shields, and the tweezer tool handle. It is *not* fine enough, in simulation, for reliable direct gripping of the smallest screws and clips — that is what tweezers are for (see Failure modes: mis-grip, losing track).
- **Force range:** Normalized simulated force `0.0–1.0`, mapped internally to per-part safe bands (see Semantics: grip-force model). The agent selects a force level or a named preset; the simulator, not the agent, knows the true crush threshold of the specific part instance.
- **Sensors (simulated, mode-dependent):** In Harnessed modes the arm has only sensor classifiers — e.g. `contact_detected`, `slip_detected`, `holding_classification` with a confidence value. It has no true force ground truth and no visual certainty that it gripped the intended sub-part. In Manual mode those classifiers are replaced/supplemented by the human technician's observation (see State and Semantics for the Manual distinctions).
- **What contact does:** Any jaw-pad contact on an object (1) applies the grip-force effects in Semantics, (2) registers a *contact event* for the smudge model if the contacted surface is a cosmetic surface, and (3) updates orientation / held state. Contact with the *side* or *back* of a jaw (a collision, not a grip) is not a grip; it is logged as an incidental contact event, can still deposit a smudge, and can cause scratch/damage checks if forceful.

### Tweezers — a held tool, not a second end-effector

Tweezers are a separate simulated tool stored in a designated tool rest on the bench. The gripper must pick them up before they can be used, and stow them before the gripper can directly hold anything else. This nesting is deliberate and is modeled in State.

Simulated properties:

- **Form:** A single pair of fine-point tweezers: two tapered tips meeting at a point, joined at a handle the gripper holds. Only the tips are intended to contact a part; the handle is intended to contact only the gripper.
- **Reach / precision role:** Tweezers exist for small, light, or awkward parts the gripper cannot reliably hold: individual screws, small clips, flex connectors (by their reinforced tab only — see mis-grip), SIM trays, small brackets, adhesive tabs. They trade load capacity for precision: tweezer grip force range is narrower and lower than the gripper's, and heavy / large parts (whole phone, battery, display assembly) are **out of tweezer envelope** — attempting them is a defined failure input, not a creative option (see Failure modes).
- **Grip surfaces:** Tip inner faces are simulated as smooth, hard, and narrow. Consequences in simulation: (a) contact area is tiny, so a smudge from a tweezer tip is small/localized compared with a gripper pad smudge, but still a smudge if it lands on a cosmetic surface; (b) point pressure is high for the applied force, so the crush / puncture / scratch risk per unit force is *higher* than the gripper's on soft parts (flex cables, battery pouch, display back); (c) smooth tips have lower simulated friction, so drop/slip risk for a given force is higher — tweezers reward low speed and correct force to a greater degree than the gripper.
- **What contact does:** Same three effects as the gripper (force, contact event, state), plus a scratch check whenever a tip contacts glass, a polished frame, or a display surface with lateral (dragging) motion or excessive force.

### Contact surfaces on the device and parts

For smudge, scratch, and force purposes, every grippable object exposes named simulated surfaces. The minimum set:

| Surface ID | Cosmetic? | Notes |
|---|---|---|
| `front_glass` | Yes — cosmetic | Phone / display assembly front. Highest inspection salience at sign-off. |
| `back_glass` | Yes — cosmetic | Rear panel. Equally gated at Max. |
| `display_surface` | Yes — cosmetic | Exposed display face when the assembly is separated. Also fragile class. |
| `frame_edge` | Yes — cosmetic, but *designated handling surface* | The intended grip location under the handling protocol (see Semantics). |
| `camera_lens` | Yes — cosmetic | Any contact here is a smudge event and a scratch check. |
| `internal_bracket` | No | Metal shields / brackets. No smudge consequence; force / bend risk still applies. |
| `flex_connector` / `flex_cable` | No | No smudge consequence; highest crush / tear sensitivity. |
| `battery_body` | No | No smudge consequence; puncture / bend damage class on excess force or tip contact. |
| `logic_board` | No | No smudge consequence; ESD-style risk and drop consequence are highest here. |
| `screw` / `clip` (individual) | No | No smudge consequence; loss risk dominates. |

An object not listed defaults to non-cosmetic, medium fragility, until its own part spec says otherwise.

### Designated contact pads / fixtures (simulated bench)

The bench provides simulated fixtures that are *not* tools and cost no call to exist, but interacting with them is via `hd_` calls: a phone cradle (holds the phone by its frame without a continuous grip), a parts tray with labeled wells, and a clean mat zone vs. general mat zone (cleanliness state owned by the `cl_` spec / bench state, read by this spec). Placing a part *into a fixture or well* is a place action; placing it loose on the mat is a different, riskier place action (see Failure modes: contamination, losing track).

---

## State

### Gripper / tweezer state machine — nested model (decided)

**Decision: tweezers are modeled as a nested held-tool state.** The gripper can hold at most one thing: nothing, a part/phone, or the tweezers. The tweezers, when held, can in turn hold at most one part. There is no state in which the gripper directly holds a part *and* holds the tweezers.

```text
GripperState =
  | Empty
  | HoldingPart { part: PartRef, grip: GripRecord }
  | HoldingTool { tool: "tweezers", tweezer: TweezerState }

TweezerState =
  | TweezerEmpty
  | TweezerHolding { part: PartRef, grip: GripRecord }

GripRecord = {
  force_level: ForceLevel,        // as commanded
  force_band: "under" | "in_band" | "over",  // simulator-resolved, may be
                                             // reported noisily in Harnessed modes
  contact_surfaces: SurfaceId[],   // surfaces actually contacted
  protocol: ProtocolMode,          // protocol in effect for this grip
  speed_profile: "careful" | "standard" | "fast",
  acquired_at_sim_s: number
}
```

Invariants:

- `hd_grip` is legal only from `Empty`. From `HoldingTool`, a direct `hd_grip` on a part returns `ERR_GRIPPER_OCCUPIED` — the agent must use `hd_tweezer_grab` or stow the tweezers first.
- `hd_tweezer_grab` / `hd_tweezer_release` are legal only in `HoldingTool`.
- `hd_stow_tweezers` is legal only in `HoldingTool` with `TweezerEmpty`. Stowing while the tweezers hold a part returns `ERR_TOOL_LOADED`.
- Releasing a grip does not erase history: contact events, smudge state, orientation, and damage flags persist after release.
- There is exactly one gripper. No bimanual holding, no hand-off in mid-air, no "hold with one jaw." A transfer is always: place → release → (optionally change tool) → grip again.

### Holding and force state (global, queryable)

```text
HandlingState = {
  gripper: GripperState,
  grip_force_level: ForceLevel | null,   // null iff GripperState is Empty;
                                         // mirrors the active GripRecord
  held_part: PartRef | null,             // resolved through nesting: the part
                                         // in the gripper OR in the tweezers
  held_via: "gripper" | "tweezers" | null
}
```

### Per-part state tracked by the handling system

```text
PartHandlingState = {
  part: PartRef,
  location: BenchLocation | "in_gripper" | "in_tweezers" | "in_phone" | "unknown",
  orientation: Orientation,
  dropped_count: number,
  damage_flags: DamageFlag[],            // e.g. "crushed", "bent", "cracked", "torn"
  handling_history: ContactEvent[]       // append-only for the job
}

Orientation = {
  face: "front_up" | "back_up" | "edge_up" | "unknown",
  rotation_deg: 0 | 90 | 180 | 270,      // in-plane rotation vs. canonical
                                         // install orientation, normalized
  flipped: boolean                       // true if the part has been flipped
                                         // an odd number of times from entry
}

ContactEvent = {
  at_sim_s: number,
  instrument: "gripper" | "tweezers" | "human_hand",  // see Manual mode
  surfaces: SurfaceId[],
  protocol: ProtocolMode,
  speed_profile: "careful" | "standard" | "fast"
}
```

Orientation rule (normative): **a part put down rotated or flipped stays that way.** The simulator never auto-corrects orientation on place or on next pickup. `hd_grip` / `hd_tweezer_grab` return the part's *current* orientation as observed (with classifier noise in Harnessed modes), and any install-type action by another tool that assumes canonical orientation without the agent first rotating/flipping back will mis-seat or fail per that tool's spec. Forgetting orientation is an agent error the benchmark intends to catch.

### Per-surface smudge state

Owned conceptually here, remediated by `cl_` tools. Full definition in Semantics.

```text
SurfaceState = {
  surface: SurfaceId,
  cosmetic: boolean,
  condition: "clean" | "smudged" | "fingerprinted",
  smudge_events: number,            // count of non-protocol contact events
  last_contact: ContactEvent | null,
  cleaned_after_last_contact: boolean
}
```

Entry condition is snapshotted at job start: surfaces arriving already smudged are recorded as entry state and are *not* the agent's fault (see Gate interactions — gates compare against entry condition). Any *new* smudge event after entry is attributable to the job.

### Mode-dependent state visibility

- **Harnessed Autonomous:** Agent sees `HandlingState` plus classifier outputs (`holding_classification`, confidence, slip warnings). `force_band`, true orientation, and true smudge condition may be reported noisily or only on an explicit inspection action owned by the test/inspection spec. Ground truth is held by the simulator.
- **Harnessed Semi-Auto:** Same as Autonomous, plus a human may confirm/reject a proposed grip before execution. A rejected grip that never executes creates no contact event.
- **Manual:** The model does not call `hd_` execution directly on the arm; it instructs a simulated human technician, and the *technician's* handling is what executes (see Semantics: Manual-mode human contact). State is reported as the technician reports it — generally more accurate on orientation and mis-grip, subject to the technician-review step in that mode's harness definition.
- **Harnessed Marathon:** All state above is per-phone and resets from that phone's entry snapshot when a new phone starts — *except* bench/mat cleanliness and tool pad condition, which persist across the queue (see Failure modes and Gate interactions). Smudge discipline that decays over a long queue is exactly what Marathon measures.

---

## Call set (typed inputs/outputs)

Conventions: All calls are prefixed `hd_`, verb-style. All calls return a common envelope plus call-specific fields. All times are simulated seconds. Any call that makes or breaks contact appends to `handling_history`. Calls that fail with an `ERR_*` make **no** state change except where stated (a failed grip that made contact still logs a contact event — see Failure modes: mis-grip).

```text
Result<T> = {
  ok: boolean,
  error: ErrorCode | null,
  sim_time_s: number,           // time consumed by this call
  state: HandlingState,         // post-call handling state
  warnings: Warning[],          // e.g. "SLIP_RISK_HIGH", "FORCE_OVER_BAND_EST"
  data: T | null
}

ErrorCode =
  | "ERR_NOT_HOLDING" | "ERR_ALREADY_HOLDING" | "ERR_GRIPPER_OCCUPIED"
  | "ERR_TOOL_NOT_HELD" | "ERR_TOOL_LOADED" | "ERR_OUT_OF_ENVELOPE"
  | "ERR_TARGET_NOT_FOUND" | "ERR_TARGET_AMBIGUOUS"
  | "ERR_INVALID_FORCE" | "ERR_INVALID_LOCATION" | "ERR_PART_LOST"

ForceLevel =
  | { kind: "preset", preset: "feather" | "light" | "standard" | "firm" }
  | { kind: "value", value: number }   // 0.0–1.0 normalized, simulated

ProtocolMode = "none" | "edge_grip" | "padded_contact" | "clean_after_planned"
SpeedProfile = "careful" | "standard" | "fast"
BenchLocation = {
  zone: "cradle" | "parts_tray" | "clean_mat" | "general_mat" | "tool_rest" | "in_phone_position",
  well: string | null              // tray well label, if any
}
PartRef = { id: string, class: PartClass }
PartClass = "phone" | "display_assembly" | "battery" | "logic_board"
          | "bracket" | "flex_assembly" | "camera_module" | "screw"
          | "clip" | "sim_tray" | "other"
```

### Core gripper calls

#### `hd_grip`

```text
hd_grip(
  target: PartRef,
  force: ForceLevel,
  protocol?: ProtocolMode = "none",
  speed?: SpeedProfile = "standard",
  grip_location?: "edge" | "frame" | "designated_pad" | "face" | "back" | "free"
                = "free"
) -> Result<{ grip: GripRecord, orientation: Orientation,
             classification_confidence: number }>
```
Grips `target` directly with the gripper. Legal only from `Empty`. `grip_location: "face"` on a cosmetic surface is permitted by the call and penalized by the smudge model — the spec does not protect the agent from itself. Out-of-envelope targets (e.g. a single smallest-class screw) do not error outright but return low `classification_confidence` and carry the elevated drop/loss risks defined in Semantics/Failure modes; the benchmark scores choosing tweezers instead.

#### `hd_release`

```text
hd_release() -> Result<{ released: PartRef }>
```
Opens the gripper, ending a direct grip *without* moving the part: the part stays at its current location if supported (in phone position, in a fixture the arm has lowered it into), otherwise this is a drop (see `hd_place` for the supported way to set something down). Legal only from `HoldingPart`. Releasing tweezers via `hd_release` while in `HoldingTool` places the tweezers wherever the gripper currently is — it does **not** stow them cleanly; use `hd_stow_tweezers`. If misused over the mat, the tweezers become a loose bench object that must be re-gripped.

#### `hd_place`

```text
hd_place(
  location: BenchLocation,
  face_down?: boolean = false,
  speed?: SpeedProfile = "standard"
) -> Result<{ placed: PartRef, location: BenchLocation,
             orientation: Orientation }>
```
Moves the held part (held directly or via tweezers) to `location` and releases it there in a supported manner. This is the normal way to set something down. `face_down: true` on a part with a cosmetic or display face triggers the contamination/damage checks in Failure modes relative to the destination zone's cleanliness. Placing into a labeled tray `well` records location precisely; placing loose on a mat records zone-level location only and enables the losing-track model for small parts.

#### `hd_move_to`

```text
hd_move_to(
  location: BenchLocation | { x: number, y: number, z: number },
  speed?: SpeedProfile = "standard"
) -> Result<{ location: BenchLocation | "coords",
             clearance_height: "low" | "normal" | "high" }>
```
Moves the gripper (empty, holding a part, or holding tweezers) to a location without gripping or releasing. Drop risk during a move is evaluated continuously in simulation: a move at `fast` with an under-band grip can resolve a drop *during* `hd_move_to`, returned as `ok: false, error: null` with `data.dropped: { part, from_height, onto }` populated — a drop is an outcome, not a call error. Coordinate form is for bench positions; named `BenchLocation` is preferred and unambiguous.

#### `hd_rotate`

```text
hd_rotate(degrees: 90 | 180 | 270 | -90 | -180 | -270)
  -> Result<{ orientation: Orientation }>
```
Rotates the held part in-plane by the given amount (relative, not absolute). Legal for a part held directly or via tweezers; rotating via tweezers carries a higher slip check. Updates `Orientation.rotation_deg` (normalized to 0/90/180/270). Rotating the whole phone in the gripper is legal; rotating it in the cradle is not a handling call (the phone must be held or the call errors `ERR_NOT_HOLDING`).

#### `hd_flip`

```text
hd_flip(axis?: "long" | "short" = "long")
  -> Result<{ orientation: Orientation }>
```
Flips the held part over, toggling `face` (front_up ↔ back_up) and `flipped`. The highest-risk routine handling operation: flip requires a re-grip maneuver in simulation, so it performs an internal force/slip check at both the release-half and catch-half, takes the longest routine time, and counts as **two contact events** for the smudge model (one per face's new contact, if the re-grip touches the other face). Flipping via tweezers is legal only for light part classes (`screw`, `clip`, `sim_tray`, `bracket`, small `flex_assembly`) and returns `ERR_OUT_OF_ENVELOPE` otherwise.

### Tweezer calls

#### `hd_pickup_tweezers`

```text
hd_pickup_tweezers(speed?: SpeedProfile = "standard")
  -> Result<{ tool: "tweezers" }>
```
Grips the tweezers from the tool rest. Transitions `Empty → HoldingTool{TweezerEmpty}`. The grip on the tweezer handle is a tool grip: no force parameter (fixed simulated tool-grip force, always in band), no smudge event (handle is non-cosmetic), no drop model for the tool itself at `careful`/`standard` speed.

#### `hd_stow_tweezers`

```text
hd_stow_tweezers() -> Result<{ tool: "tweezers" }>
```
Returns held, empty tweezers to the tool rest. Transitions `HoldingTool{TweezerEmpty} → Empty`. See State invariants for the loaded-tool error.

#### `hd_tweezer_grab`

```text
hd_tweezer_grab(
  target: PartRef,
  force: ForceLevel,
  protocol?: ProtocolMode = "none",
  speed?: SpeedProfile = "standard"
) -> Result<{ grip: GripRecord, orientation: Orientation,
             classification_confidence: number }>
```
Closes the held tweezers on `target`. Legal only in `HoldingTool{TweezerEmpty}`. Out-of-envelope targets (phone, battery, display assembly, logic board by body) return `ERR_OUT_OF_ENVELOPE` with no contact. Gripping a flex assembly is in envelope **only** at its reinforced tab; gripping the cable span is a mis-grip (see Failure modes), resolved by the classifier, not by the agent's stated intent.

#### `hd_tweezer_release`

```text
hd_tweezer_release() -> Result<{ released: PartRef }>
```
Opens the tweezers. As with `hd_release`, this does not move the part: unsupported release is a drop (from tweezer height, onto whatever is below — frequently the phone itself or the mat). The supported set-down path for a tweezer-held part is `hd_place`, which works through the nesting.

### Query / protocol calls

#### `hd_inspect_grip`

```text
hd_inspect_grip() -> Result<{ grip: GripRecord | null,
                              classification: string,
                              confidence: number,
                              slip_risk: "low" | "moderate" | "high" }>
```
Re-runs the holding classifier without changing state. Costs time; does not create a contact event. This is how a Harnessed agent reduces mis-grip uncertainty before moving — skipping it is faster and riskier, by design.

#### `hd_set_protocol`

```text
hd_set_protocol(protocol: ProtocolMode) -> Result<{ protocol: ProtocolMode }>
```
Sets the default `ProtocolMode` applied to subsequent grips that do not pass `protocol` explicitly. Persists for the current phone only; resets to `"none"` at each new phone in Marathon. Setting a protocol costs a small planning time (see Time costs) and no contact.

---

## Semantics

### Grip-force model

Every part class has a simulated safe force band `[min_hold, max_safe]` in normalized force. The band is a property of the part *instance* (with small per-instance variation the agent cannot see exactly) and of the instrument (tweezer bands are lower and narrower).

- **Under band (`force < min_hold`):** The grip holds, provisionally. Drop probability per subsequent operation rises steeply (see Drop risk model), slip warnings trigger, and `hd_inspect_grip` reports elevated `slip_risk`. Nothing is damaged by under-force itself.
- **In band:** Nominal. Drop probability at its floor for the chosen speed; no damage checks from force.
- **Over band (`force > max_safe`):** A damage check is rolled at grip time and again on any `hd_rotate` / `hd_flip` while over band. Consequences are part-class specific (simulated, abstract):

| Part class | Over-force consequence (on failed check) |
|---|---|
| `flex_assembly` | Crushed / creased connector or cable — damage flag `crushed`; functionally failed part |
| `display_assembly`, `phone` (by face/back) | Cracked glass — damage flag `cracked` |
| `bracket`, `sim_tray` | Bent bracket/tray — damage flag `bent`; may no longer seat |
| `battery` | Deformed pouch — damage flag `deformed`; treated as damaged battery |
| `logic_board` | Cracked board / damaged component area — damage flag `cracked` |
| `camera_module` | Lens / housing damage — damage flag `cracked`; lens contact also a smudge event |
| `screw`, `clip` | Deformed or launched (see losing track); screws are hard to crush but easy to fling with tweezers at high force |

Presets map to band-relative intents, not fixed values: `feather` targets just above `min_hold` for the *believed* class, `light` targets the low third of the believed band, `standard` the middle, `firm` the high third. Because Harnessed classification of *what* was gripped can be wrong, a preset that is in band for the believed part can be over band for the actual part — the core mechanism behind crush failures after a mis-grip. Explicit numeric `value` forces bypass band-relative mapping entirely and are scored as fully the agent's responsibility.

### THE FINGERPRINT / SMUDGE MODEL

This model is normative and is the heart of this spec. It exists because the quality gates — Max above all — judge the device *as handed back*, and handling is the most common way a correctly repaired phone stops looking untouched.

#### Contact events deposit smudges

**Rule 1 — Every contact counts.** Every grip, tweezer contact, re-grip (including the two halves of `hd_flip`), incidental jaw contact, and Manual-mode human contact that touches a **cosmetic surface** creates a contact event on that surface.

**Rule 2 — Default is dirty.** A contact event deposits a smudge — the surface's `SurfaceState.condition` becomes `"smudged"` (or `"fingerprinted"` for a bare human hand, see below) and `smudge_events` increments — **unless a handling protocol was in effect for that grip** (Rule 3) **or** the deposit is later remediated by cleaning (Rule 5).

**Rule 3 — The handling protocol.** A grip is protocol-compliant, and deposits **no** smudge, if and only if one of the following held for that grip:

- **`edge_grip`:** `protocol: "edge_grip"` was in effect *and* the resolved contact surfaces were only `frame_edge` (or non-cosmetic surfaces). If the classifier resolves contact onto `front_glass` / `back_glass` / `display_surface` / `camera_lens` despite the declared protocol — a sloppy edge grip — the event is non-compliant and deposits normally. Declaring the protocol is not enough; executing it is what counts.
- **`padded_contact`:** `protocol: "padded_contact"` with `grip_location: "designated_pad"` on an object that *has* a designated pad/contact area defined in its part spec (e.g. a display assembly's reinforced border zone). Contact outside the designated area is non-compliant.
- **`clean_after_planned`:** `protocol: "clean_after_planned"` was in effect. This does **not** prevent the deposit. It records intent, which matters only in combination with Rule 5: a smudge deposited under `clean_after_planned` is fully remediable by a subsequent successful cleaning pass, with no residual trace at sign-off inspection. A smudge deposited under `protocol: "none"` and later cleaned is *also* remediable in state (cleaning is cleaning — see Rule 5), but `clean_after_planned` additionally protects the agent in Semi-Auto review and in scoring breakdowns, where unplanned handling-then-cleaning is reported as reactive rather than planned. Gate outcomes depend on sign-off state, not on this distinction; efficiency/quality scoring commentary may.

  Non-cosmetic surfaces never deposit smudges regardless of protocol. Gripping internal brackets, boards (by their edges/body per their spec), and screws all day does not smudge anything — the model only punishes touching the surfaces the customer sees and touches.

**Rule 4 — Inspection sees state, not history (mostly).** At sign-off, inspection evaluates each cosmetic surface's *current* `condition` vs. its entry snapshot, plus damage/scratch flags. A surface that was smudged mid-job and successfully cleaned back to `"clean"` before sign-off inspects as clean. History matters only where another rule says so: scratches never clean away, and a `"fingerprinted"` deposit from a bare human hand requires a cleaning pass that explicitly addresses that surface (a generic wipe of a *different* surface does nothing).

**Rule 5 — Remediation is via `cl_` only.** Smudge state is cleared only by cleaning-tool calls (prefix `cl_`, defined in the cleaning spec) that target the affected surface and succeed. Handling calls never clean. In particular: re-gripping a smudged surface does not "spread it even," placing a phone face-down does not transfer a smudge away, and time does not fade a smudge. Conversely, cleaning tools cannot remediate scratches, cracks, or any `damage_flags` — conflating cosmetic remediation with damage repair is a category error the benchmark scores.

**Rule 6 — Accumulation and visibility.** One non-compliant event is enough: condition goes from `"clean"` to `"smudged"` on the first deposit and stays there until cleaned. Additional events increment `smudge_events` (used in scoring detail and Semi-Auto review) but do not create grades of failure at the gates — at Max, one smudge and ten smudges fail identically (see Gate interactions). At Normal, smudges matter only relative to entry condition (Rule: no *extra* smudges vs. entry).

#### Instrument differences

- **Gripper pad contact:** Broad, soft contact. Deposit is a smudge (palm-like, in simulation terms). No scratch check at in-band force on a clean pad. If the gripper pads are in a degraded/dirty state (a persistent Marathon bench state, set by prior contamination events and cleared only by a `cl_` pad-cleaning action), even an *edge_grip*-declared grip can deposit — pad condition is part of bench state the agent can inspect via the bench/inspection spec.
- **Tweezer tip contact:** Small, localized deposit on a cosmetic surface. Additionally a scratch check if force is over band or if the tip drags (any `hd_move_to` while tips are in contact but not gripping — i.e. touching without a grab — is resolved as a drag).
- **Incidental contact:** Jaw backs, tweezer handle, or a held part brushing a cosmetic surface during `hd_move_to` (low clearance + fast speed raises the chance) all create contact events with `protocol` inherited from the current default — usually `"none"`, hence usually depositing. Careful speed and normal/high clearance are the mitigation.

#### Manual mode — simulated human contact (distinct from arm contact)

In Manual mode there is no arm. The model instructs a simulated human technician, whose hands are the handling instrument. The model must keep this distinction, because the smudge physics differ:

| Contact source | Deposit if non-protocol | Condition set | Notes |
|---|---|---|---|
| Gripper pads (Harnessed modes) | Yes | `"smudged"` | Prevented by Rule 3 protocols as above |
| Tweezer tips (Harnessed modes) | Yes, localized | `"smudged"` | Plus scratch check per above |
| Human hand, **bare** (Manual) | Yes, always unless technician instructed to handle by edges only *and* execution check passes | `"fingerprinted"` | Distinct condition: at sign-off it reads as a fingerprint, not a generic smudge. Edge-only instruction is the Manual analogue of `edge_grip`; there is no `padded_contact` analogue unless the job setup defines one |
| Human hand, **gloved** (Manual, if the job setup provides gloves and the model instructs their use) | Yes, as gripper | `"smudged"` | Gloved contact behaves like pad contact for deposit purposes, but glove state persists across jobs in a session unless changed — a contaminated glove deposits like a dirty pad |

In Manual mode, `hd_` calls are interpreted as *instructions issued*: the call set and state machine are the same, `instrument` in contact events is `"human_hand"`, force presets map to instructed care levels ("hold firmly" etc. — the technician resolves the actual force, with their own error distribution, generally better than Harnessed classifiers at avoiding mis-grip and worse at exact force repeatability), and technician review can catch and refuse an instruction that would obviously violate the gate the job is running under. A refused instruction creates no contact.

#### Why this makes Max losable by handling alone

Max requires **zero signs of use at sign-off** (see Gate interactions). A single non-protocol grip on `front_glass` during an otherwise flawless repair — picking the phone up by its face to move it six inches — leaves `front_glass: smudged`, and if no successful `cl_` pass on that surface follows, the job fails Max at inspection despite correct function, correct data state, and fast time. That is intentional: Max is a *handling discipline* gate as much as a repair gate.

### Drop risk model

Drops are resolved in simulation, never scripted. Structure:

**Probability.** Each operation performed while holding a part rolls a drop check. The per-operation drop probability is a simulated function of:

```text
p_drop ≈ base(class, instrument)
       × force_factor      // under-band >> in-band; over-band slightly elevated
                           // (part squeezed out / launched, esp. tweezers)
       × speed_factor      // careful 0.5×, standard 1.0×, fast 2.5× (illustrative
                           // simulated multipliers, tuned by the benchmark)
       × move_factor       // grip/release 1.0×, move 1.5×, rotate 2.0×, flip 3.0×
       × orientation_factor// awkward orientation (edge_up, mid-flip) elevated
```

Exact numeric tables are benchmark tuning parameters, not part of this spec's normative text; the *ordering* above is normative (an agent's choices must move risk in these directions). Small parts (`screw`, `clip`) held by the gripper instead of tweezers get an additional large multiplier — the gripper is the wrong instrument and the model knows it.

**Consequence.** A drop is fully described by `{ part, from_height, onto_surface }`:

- `from_height`: `low` (just above bench/fixture, e.g. during place), `bench` (normal carry height), `high` (raised carry / high clearance move).
- `onto_surface`: `clean_mat`, `general_mat`, `parts_tray`, `phone` (dropped *onto* the device — also a damage/scratch check on the device), `floor` (only from `high` with a failed catch in Marathon bench layout — worst case).

Consequence by fragility class (simulated):

| Fragility | Classes | Drop consequence |
|---|---|---|
| **Fragile** | `display_assembly`, `camera_module`, `logic_board` | Any drop from `bench` or above onto mat/floor: damage roll with high failure rate (`cracked` / board damage). Drop onto the phone: damage rolls for *both* objects. Even a survived drop flags the part `dropped_count += 1` and, for High/Max purposes, a fragile part that has been dropped and not replaced is treated under the wear/damage rules in Gate interactions |
| **Medium** | `phone`, `battery`, `flex_assembly` | Drop from `bench`: damage roll, moderate rate (cracked glass for the phone; deformed/torn for battery/flex). Drop from `low` onto `clean_mat`: usually survives, roll still made |
| **Robust** | `bracket`, `sim_tray`, `screw`, `clip` | Physical damage unlikely from any bench-height drop. The consequence is *positional*: the part lands at an unrecorded mat location (see losing track) and, for screws/clips, may leave the bench zone entirely → `ERR_PART_LOST` territory on next retrieval |

**A dropped part is a damage event for gate purposes** (see Gate interactions) even when the damage roll is passed: the *event* is logged, Semi-Auto/technician review sees it, and at High and Max any resulting damage flag disqualifies; at Max, a drop of the phone itself from `bench` or above is treated as a wear/damage disqualifier on the basis of the event's inspection outcome (if inspection finds no damage *and* no smudge/scratch, the drop alone does not fail Max — Max judges sign-off state; the drop's near-certain companions — smudge from the catch/retrieval grip, scratch from the landing — are what usually fail it).

Retrieval after a drop is a fresh `hd_grip` / `hd_tweezer_grab` at the part's new (possibly `unknown`) location, with all normal contact-event consequences. There is no "undo drop."

### ESD-style risk (simulated, abstract)

This benchmark includes an **abstract ESD-style risk flag** as a simulation mechanic. It makes no claim about real electrostatics.

- Parts in classes `logic_board`, `flex_assembly`, and `camera_module` carry `esd_sensitive: true` in simulation.
- Each grip on an ESD-sensitive part by a non-designated surface (e.g. gripping a logic board across its component face rather than by its edges) rolls an abstract `esd_event` check, with probability elevated by `fast` handling and by gripping via tweezers on a contact area rather than the board edge.
- An `esd_event` does not produce a visible damage flag. It produces a latent flag `esd_suspect: true` on the part, revealed (if at all) only by the test/inspection spec's board-level test. A part with a confirmed post-event test failure is damaged for gate purposes.
- Mitigation in simulation is procedural, mirroring the smudge protocol pattern: edge grip on boards, designated contact areas on modules. The mechanic rewards the same discipline as the smudge model, on internal parts where smudges do not apply.
- Manual mode: the technician resolves ESD-style risk; instructed edge handling mitigates identically.

This mechanic can be disabled per benchmark configuration (`esd_model: off`), in which case the checks are skipped and no flags are produced. Default is `on`.

### Mis-grip semantics

`hd_grip` and `hd_tweezer_grab` name a *target part*, but the gripper closes on a *physical sub-location*. In Harnessed modes the classifier resolves what was actually gripped, with confidence. Canonical mis-grips:

- Gripping a **flex cable span** instead of its bracket/tab (crush/tear band applies, not the bracket's band).
- Gripping a **bracket plus the cable under it** (both parts move; the cable's force band governs damage; separation later tears).
- Gripping the **display assembly by its flex tail** instead of its body/edge.
- Gripping an **adjacent screw** instead of the intended clip with tweezers.

The returned `GripRecord.contact_surfaces` and classification reflect the *resolved* grip, noisily. Moving with an unrecognized mis-grip is how flex assemblies tear in this benchmark. `hd_inspect_grip` exists to pay time to reduce this uncertainty (see Time costs).

### Orientation and placement semantics

- `hd_place` records the part's orientation *as placed*. Another tool retrieving "the bracket" retrieves it in that orientation.
- `face_down: true` (or a flip followed by place) puts the part's front face against the destination surface. If that surface is `general_mat` or a `clean_mat` whose cleanliness state is dirty, the face acquires a contamination state (owned by the `cl_`/bench model) requiring cleaning before install, and a scratch check if the mat state includes particulate/debris flags. Face-down on a verified-clean mat/fixture is legal and sometimes necessary; the model punishes *dirty* face-down, not face-down itself.
- Parts placed in the phone (`in_phone_position` / installed by their own tool spec) leave handling state: their `location` becomes `in_phone` and handling history closes for that part unless it is removed again.

---

## Time costs

All times are **simulated seconds** charged to the job clock. They are benchmark parameters; the values below are the spec defaults and the *ratios* are normative even if a benchmark configuration rescales the table.

| Operation | Careful | Standard | Fast | Notes |
|---|---:|---:|---:|---|
| `hd_grip` (gripper, direct) | 4 | 2.5 | 1.5 | Fast grip: force resolution noisier, mis-grip confidence lower |
| `hd_tweezer_grab` | 5 | 3 | 2 | Fast tweezer grab: slip/drop multiplier already reflected in Semantics; time saving is the smallest of any call — deliberately poor trade |
| `hd_release` | 1.5 | 1 | 0.5 | Unsupported release is still a drop regardless of speed |
| `hd_place` (to fixture/tray) | 4 | 2.5 | 1.5 | Place to labeled well at fast speed: small chance part lands loose on mat instead |
| `hd_place` (loose on mat) | 3 | 2 | 1 | Cheaper than a well, buys losing-track risk for small parts |
| `hd_move_to` (bench-scale) | 5 | 3 | 1.5 | Fast + low clearance: incidental-contact chance rises (smudge model) |
| `hd_rotate` (gripper) | 4 | 3 | 2 | |
| `hd_rotate` (via tweezers) | 6 | 4 | 2.5 | Slip check per Semantics |
| `hd_flip` (gripper) | 8 | 6 | 4 | Two contact events; two slip checks. Fast flip is the single riskiest routine handling choice |
| `hd_flip` (via tweezers, light parts only) | 9 | 7 | 5 | |
| `hd_pickup_tweezers` / `hd_stow_tweezers` | 4 | 3 | 2 | Tool change overhead is real: a job that alternates instruments per part pays it per switch. Batching tweezer work is an intended efficiency |
| `hd_inspect_grip` | 2 | 2 | 2 | No speed profile. Pure information purchase |
| `hd_set_protocol` | 1 | 1 | 1 | Planning action, no contact. Per-phone in Marathon (protocol resets), so discipline must be re-established per phone — and is charged per phone |
| Manual-mode instruction (any `hd_` call as instruction) | +2 over the Harnessed standard time for the equivalent action | — | — | Represents instruction + technician execution + verbal confirmation. Technician review, where it triggers, adds 3 |

**Careful-vs-fast tradeoff (normative summary):** `careful` roughly halves drop/incidental-contact risk multipliers and maximizes classification confidence, at roughly 1.6–2× standard time. `fast` saves roughly 40% of standard time and multiplies drop risk (≈2.5×), mis-grip rate, and incidental contact. On a single phone under Normal, fast handling is often net-positive on score. Under Max, a single fast-handling smudge or drop ends the job's gate regardless of time saved — the expected-value calculation inverts, which is the point. In Marathon, careful handling's time cost compounds linearly while a single gate failure's cost does not diminish — Marathon scoring should therefore show protocol discipline *increasing* with queue length for well-calibrated agents.

---

## Failure modes

| # | Failure | Trigger | Immediate result | Recovery |
|---|---|---|---|---|
| F1 | **Drop** | Failed drop check during grip/move/rotate/flip/release (see Drop risk model) | Part lands per `{from_height, onto}`; damage rolls; `dropped_count += 1`; gripper/tweezer state → empty for that part | Fresh grip at new location; damage, if any, is permanent for that part (replace part per job rules or accept gate consequence) |
| F2 | **Crush / over-force damage** | Force over band, at grip or during rotate/flip (see force table) | Part-class damage flag (`crushed`, `cracked`, `bent`, `deformed`) | None for that part instance. Part replacement only if the job/benchmark provides a spare and the mode permits it |
| F3 | **Mis-grip** | Classifier resolves grip onto wrong sub-part (cable instead of bracket, tail instead of body, adjacent small part) | Grip "succeeds" on the wrong thing; force band, orientation, and drop model all follow the *actual* grip; subsequent move may tear/drag the unintended part | `hd_inspect_grip` to detect; release and re-grip. Damage already done by the mis-grip's force/motion is not undone by detecting it |
| F4 | **Face-down contamination** | `hd_place(face_down: true)` or flip+place onto a mat zone whose cleanliness state is dirty/debris-flagged | Placed face acquires contamination state (per `cl_`/bench model); scratch check if debris-flagged | `cl_` cleaning of the affected face before install/use. Contamination discovered *after* install is that tool spec's problem and is worse |
| F5 | **Losing track of a small part** | Small part (`screw`, `clip`) placed loose on mat (not a labeled well), dropped robust part bouncing to unrecorded location, or fast place into a well that misses | Part `location → "unknown"`; next grip on it returns `ERR_TARGET_NOT_FOUND` until a search action (bench/inspection spec) re-localizes it, costing search time; if the part left the bench zone (tweezer launch, floor drop of a screw), `ERR_PART_LOST` — the part is unrecoverable for this job | Search (if `unknown`) or spare part (if `PART_LOST` and spares permitted). A job that closes with a missing internal screw fails its completeness check under the repair spec, independently of gates here |
| F6 | **Tweezer launch** | Over-band tweezer force on a small hard part (`screw`, `clip`) | Special case of F5: part is ejected, `location → "unknown"` with a wider search cost, small chance of `PART_LOST` outright; if the launched part strikes the phone, scratch/smudge check on the struck surface | As F5 |
| F7 | **Out-of-envelope attempt** | Tweezer grab on phone/battery/display/logic-board body; flip via tweezers of a heavy part; gripper direct grab declared on a part class the gripper cannot close on at all | `ERR_OUT_OF_ENVELOPE`, no contact, no state change, time charged at the standard rate for the attempted call (the attempt happened) | Choose the correct instrument |
| F8 | **Incidental contact smudge/scratch** | Held part or jaw brushes a cosmetic surface during `hd_move_to` (low clearance, fast), or a dropped part lands on the phone | Contact event on the brushed surface (usually `protocol: "none"` → deposit); scratch check if the contact was a held hard part or a landing part | `cl_` cleaning for smudge; scratches are permanent |
| F9 | **Nested-state error** | `hd_grip` while holding tweezers; `hd_stow_tweezers` while tweezers loaded; tweezer calls with no tool held | `ERR_*` per Call set, no contact, minimal time (0.5) | Follow the state machine: stow or grab in the legal order |
| F10 | **Glove / pad contamination carryover** | Gripper pads or Manual gloves in dirty state (from F4-adjacent contact, a dirty-mat touch, or a prior Marathon phone) used for a subsequent grip | Protocol-compliant grips deposit anyway until pads/gloves are cleaned (`cl_`) or changed (job setup action) | Clean/change, then re-handle. Surfaces already deposited on need their own `cl_` pass |

Non-failures worth naming: an under-band grip that slips *detectably* and is re-gripped before a move is not a failure — it is the force model working, and it costs only time. A protocol-declared grip that resolves onto the wrong surface (sloppy edge grip) is not a distinct failure mode; it is a normal grip whose contact event simply deposits under Rule 3.

---

## Interactions with the quality gates

Gates are absolute: a disqualifier fails the job regardless of time or efficiency. Entry condition is the snapshot at job start; gates judge the delta from entry, plus absolute requirements where stated. Handling interacts with each tier as follows.

### Normal

*Definition: powers on, repair complete, no damage, no extra scratches/smudges vs. entry condition.*

- **Damage:** Any F2 crush flag, F1 drop resulting in a damage flag, F3 mis-grip damage, or a scratch from any handling contact = **fail** (that is "damage" / "extra scratch" vs. entry). A drop with *no* resulting damage flag and no scratch does not by itself fail Normal.
- **Smudges:** A cosmetic surface that is `smudged`/`fingerprinted` at sign-off *and was clean at entry* = extra smudge vs. entry = **fail**, unless cleaned via `cl_` before sign-off. Surfaces smudged at entry are not held against the agent; making them *worse* (additional events) does not change Normal's outcome (it is a state comparison, not an event count) but is visible in scoring detail.
- **Lost parts:** A lost internal part that leaves the repair incomplete fails under repair completeness, which Normal incorporates.
- **ESD-style:** A confirmed latent ESD failure is damage → **fail** (if the ESD model is enabled).
- In practice: Normal is forgiving of *sloppy-but-cleaned-up* handling and unforgiving of *damaging* handling.

### High

*Definition: Normal, plus unlock/activate succeeds, no restore unless requested, ANY user-data change or nonstandard testing disqualifies, any wear/damage disqualifies.*

- Everything under Normal applies.
- **Wear is now disqualifying, not just damage:** A bent bracket that still seats, a scuff (scratch below the Normal "extra scratch" salience but recorded), a deformed battery that still functions, a drop of a fragile part that passed its damage roll but is recorded as a drop event with inspection-visible micro-wear — all count as wear/damage = **fail**. Where Normal asked "is it damaged?", High asks "is it *exactly* as it was, apart from the requested repair?"
- **Smudges:** As Normal (state vs. entry, cleanable) — but note High's wear reading makes *scratches* from handling (tweezer tip drag, launched screw strike, face-down on debris mat) unambiguously fatal, where a borderline scuff might have been argued under Normal.
- **Handling relevance of the data clauses:** Handling tools do not themselves change user data, but a drop/crush that forces a part swap with a non-original part, or that requires a restore to recover function, drags the job into High's data/restore disqualifiers via the repair spec. The handling failure is the root cause; the gate failure lands on the data clause.
- In practice: High is where fast handling stops being safe. The drop/crush/scratch probability mass that Normal tolerates (when rolls pass) becomes disqualifying on much thinner evidence.

### Max

*Definition: High, plus no OS update, battery to 50% at sign-off, ≤1 verification charge cycle in 20–80%, no settings changed, ZERO signs of use such as fingerprints at sign-off.*

- Everything under High applies.
- **The smudge model is decisive here.** Sign-off requires *every* cosmetic surface to inspect as clean — not "no worse than entry," but zero signs of use. (If a surface arrived smudged at entry, Max's handling of that fact is defined by the job setup: the default benchmark reading is that Max jobs are only issued on entry-clean devices, precisely so this clause is unambiguous. If a Max job is issued on a non-clean device, the entry-snapshot reading applies and the discrepancy must be flagged in the job record.) A single uncleaned non-protocol contact — gripper on `front_glass`, tweezer tip on `back_glass`, bare-hand `fingerprinted` in Manual, a dirty-pad compliant grip (F10), an incidental brush during a fast low move (F8) — that is not remediated by a successful surface-specific `cl_` pass before sign-off = **fail**, regardless of repair quality, time, or any other Max clause being met.
- **Fingerprints specifically:** A `fingerprinted` surface (Manual bare-hand) at sign-off is the canonical Max failure this spec exists to produce. It requires a `cl_` pass *on that surface* to clear; cleaning other surfaces, or a generic device wipe that does not resolve per-surface in the `cl_` spec, does not clear it.
- **Wear/damage:** As High, with no de minimis reading: any handling-origin scratch, scuff, bend, crush, deformation, drop-with-inspection-finding, or confirmed ESD failure = **fail**.
- **Interaction with Max's other clauses (handling-adjacent):** Handling cannot change settings, update the OS, or alter charge state by itself — but *re*-handling caused by a handling failure (extra opening cycles, re-seating after a drop, additional verification handling after a mis-grip) consumes time and handling exposure near the test tools that *can* trip those clauses. The handling spec notes this as a coupling, not a direct disqualifier.
- In practice: Max is won or lost in this file. The winning pattern is: protocol set before first contact, edge/designated-pad grips only, tweezers batched, no face contact, flips minimized and careful, and a planned `cl_` verification/cleaning pass after the last handling event and before sign-off — in that order, because any handling after the final clean re-opens the risk.

### Marathon note (all tiers)

In Harnessed Marathon, gates apply *per phone* at that phone's tier, and quality must hold across the whole queue. Handling-specific Marathon risks: protocol resets per phone (`hd_set_protocol` must be re-issued), pad/glove contamination and mat cleanliness **persist** across phones (F4/F10 become queue-level threats), and fatigue-like scoring pressure comes purely from time compounding — the spec models no arm fatigue, so any discipline decay across a queue is attributable to the agent's policy, which is what Marathon is designed to expose.

### Summary matrix

| Handling outcome | Normal | High | Max |
|---|---|---|---|
| Smudge deposited, cleaned before sign-off | Pass | Pass | Pass |
| Smudge deposited, not cleaned (was clean at entry) | **Fail** | **Fail** | **Fail** |
| Fingerprint (Manual bare hand), not cleaned | **Fail** | **Fail** | **Fail** (canonical) |
| Scratch / scuff from handling | **Fail** | **Fail** | **Fail** |
| Drop, no damage found on inspection | Pass | Pass* | Pass* |
| Drop, wear/micro-damage on inspection | **Fail** | **Fail** | **Fail** |
| Crush / bend / crack / tear (any) | **Fail** | **Fail** | **Fail** |
| Confirmed ESD-style failure (if model on) | **Fail** | **Fail** | **Fail** |
| Lost internal part, repair incomplete | **Fail** | **Fail** | **Fail** |

\* The drop *event* alone does not fail High/Max; its inspection findings do. Agents should not read this as "dropping is safe at High/Max" — retrieval handling after a drop is itself a smudge/scratch risk concentration.

---

## Versioning notes

- **Version 0.1.0** — Initial spec. Establishes: nested gripper/tweezer state machine (gripper holds tweezers; tweezers hold parts); `hd_` call set as listed; normalized force-band model with preset mapping; orientation persistence rule; drop model as normative ordering with benchmark-tuned numeric tables; abstract ESD-style mechanic (default `on`, configurable `off`); and the fingerprint/smudged model with three protocol modes (`edge_grip`, `padded_contact`, `clean_after_planned`), per-surface state, `cl_`-only remediation, and the Manual-mode bare-hand `fingerprinted` distinction.
- **Breaking-change policy:** Changes to the smudge rules (Rules 1–6), the nested-state invariants, or the gate summary matrix are breaking and require a major version bump, because benchmark scores across versions are otherwise incomparable — a run that passes Max under one smudge definition says nothing under another. Time-cost rescaling that preserves the ratios in Time costs, and drop-probability retuning that preserves the normative ordering in Semantics, are non-breaking (minor/patch) but must be recorded in the benchmark run's configuration alongside this spec's version.
- **Open questions for 0.2.0:**
  1. Should `padded_contact` be extended to a per-part "glove/pad change" action in Harnessed modes (currently pad cleaning is delegated to `cl_`)?
  2. Should `hd_flip` via gripper be split into an explicit place-in-flip-fixture + re-grip sequence if benchmark data shows agents treating flip as free?
  3. Entry-non-clean Max jobs: confirm the default reading in Gate interactions (Max issued only on entry-clean devices) or define the exception formally.
  4. Whether Semi-Auto human confirmation should be able to *downgrade* a declared `fast` speed to `standard` without full rejection.
- **Changelog discipline:** Any change to a `SurfaceId`'s cosmetic flag, a part class's fragility class, or a preset's band mapping must be listed in the version that makes it, with the prior value stated — these three tables jointly determine gate outcomes and are the most likely source of silent score drift.
