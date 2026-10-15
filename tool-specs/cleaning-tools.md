# Cleaning Tools — Tool Spec (`cl_`)

> **SIMULATED SYSTEM — DESIGN SPECIFICATION ONLY**
>
> This document specifies tools, state, costs, and failure behaviour for a
> *simulated* robotic phone-repair arm benchmark. All tools, surfaces,
> contaminants, sensors, times, and effects described here are simulation
> constructs with simulation-defined properties. Nothing in this file is a
> claim about any real-world product, solvent, material, device, or cleaning
> procedure, and nothing here is a procedure for use on a real phone.

| Field | Value |
|---|---|
| Tool prefix | `cl_` |
| Job class served | Maintenance — deep-cleaning (explicit job class), plus final-pass cleaning on any job |
| Related specs | Handling tools (`hd_`, smudge model), inspection tools, assembly tools |
| Modes | Harnessed Autonomous, Harnessed Semi-Auto, Manual, Harnessed Marathon |
| Benchmark scoring axes | Time, efficiency, accuracy |

---

## 1. Purpose

The cleaning tools remove simulated contaminants from simulated phone
surfaces, restore a surface to its entry condition (or better, where the
job requests it), and — uniquely among the tool families — make the Max
quality gate reachable at all.

Functions served:

1. **Deep-cleaning jobs.** Maintenance jobs whose requested work *is*
   cleaning: remove accumulated dust, grime, oils, and residue from the
   exterior, meshes, ports, and (when the phone is already open for other
   work) internal surfaces.
2. **In-process cleaning.** Removing debris generated or exposed by other
   work (e.g. loose dust inside an opened phone) before reassembly, so it
   is not sealed inside.
3. **Final-pass cleaning.** The terminal cleaning sequence performed after
   the *last* handling event on a reassembled phone. Per §5, this is the
   only route to the Max gate's "zero signs of use" end state.

Cleaning is deliberately the benchmark's principal time sink (§6). Most
of its cost is not the strokes themselves but consumable changes, drying
waits, and re-inspection. The scoring tension is intentional: skipping
steps is fast and usually invisible until a quality gate checks the end
state, at which point the failure is absolute.

Cleaning tools do **not** repair damage, remove scratches, restore
coatings, or clean user data. Removing a contaminant is not the same as
undoing a damage event (§7).

---

## 2. Physical description (simulated)

All descriptions are of the simulated end effectors and their simulated
consumables. Each tool is mounted or staged within arm reach; tool change
and consumable change are timed operations (§6).

### 2.1 Brushes

A set of simulated brushes differing only in simulation parameters
(stiffness class, width class). No other physical property is modelled.

| Brush | Stiffness | Intended simulated surfaces | Notes |
|---|---|---|---|
| Soft brush | Soft | Glass, frame, board | Sweeps loose material; cannot scrub |
| Detail brush | Soft, narrow | Speaker mesh, port rim, seams, camera surround | Reaches recesses the soft brush bridges over |
| Firm brush | Firm | Frame, port interior | Only brush with any effect on adhered grime; barred from coated glass (§5.4) |

- A brush pass moves loose contaminant *somewhere*: off the surface,
  across the surface, or into an adjacent recess, depending on stroke
  direction and what borders the target (§5.2). It captures nothing.
- Brushes accumulate picked-up contaminant as they work (§3).

### 2.2 Compressed air

A simulated air nozzle with a regulated pressure setting
(`low | medium | high`) and a modelled angle of application relative to
the target surface.

- Effective at ejecting loose, dry contaminant from recesses a brush or
  wipe cannot reach (port interior, speaker mesh, seams).
- Captures nothing: ejected contaminant leaves the target along the
  airflow path, and the simulator settles a fraction of it on adjacent
  surfaces (§5.2).
- Angle and pressure are first-class parameters, not flavour — they
  decide whether a blast cleans a recess or drives contaminant deeper
  into it (§5.2, §7).
- Pressure limits apply near microphones and meshes (§5.5).

### 2.3 Wipes

Flat simulated wipes, dispensed one at a time, each individually tracked
by `wipe_id`. A wipe is the only cleaning tool that *captures* contaminant
(it lifts and holds oils, grime, and residue) — and the only one whose
effectiveness inverts with use: a loaded wipe redeposits what it holds
(§3, §7).

- **Dry wipe** — for dust pickup, drying, and post-solvent pickup.
- **Pre-moistened wipe** — a wipe the simulator treats as already carrying
  a fixed, small solvent load; enters the wet-state model (§5.3) on
  contact and cannot be re-wetted or topped up.
- Wipes are single-surface-class in effect: a wipe used on a port or mesh
  sheds fibres in the simulation (fibre residue, §5.1) and is thereafter
  barred from glass.

### 2.4 Solvents

A simulated solvent dispensed from a reservoir in metered amounts
(`amount` in abstract simulation units, §4). "Solvent" here is a single
simulation substance class with the properties defined in §5 — it is not
modelled on, and makes no claim about, any real substance.

- Loosens adhered grime and dissolves oils so a wipe or brush can remove
  them; on its own it removes almost nothing — it *mobilises* contaminant,
  which must then be picked up before drying (§5.3).
- Behaviour differs by surface coating class (§5.4): on a coating class
  marked solvent-sensitive in the simulation, application is a damage
  event, not a cleaning action.
- Dispensing is metered from a finite reservoir (§3); over-application is
  a modelled, common failure (§7).

### 2.5 Ancillary simulated items

| Item | Role in simulation |
|---|---|
| Waste bin | Destination for used wipes and captured debris; `cl_dispose_wipe` is timed |
| Wipe dispenser | Issues the next fresh wipe with a new `wipe_id`; finite stock per job (§3) |
| Solvent reservoir | Finite per job; level checked by `cl_solvent_level` |
| Drying rest | The phone (or part) sits untouched while wet state decays; no tool, but `cl_dry_wait` occupies the arm/bench in the timing model (§6) |

---

## 3. State

State is per-job unless noted. All state below is simulator-visible to the
harness; in Harnessed Autonomous mode the agent learns it only through
the call returns and inspection tools specified elsewhere — there is no
free read of ground-truth contamination (§5.6).

### 3.1 Surface state (per surface instance)

Surfaces are addressed by a `surface` identifier whose class is one of:
`glass`, `frame`, `speaker_mesh`, `port_interior`, `board`. A phone has
multiple instances per class (e.g. front glass, rear glass, each mesh,
each port).

For each surface instance:

| Field | Type | Meaning |
|---|---|---|
| `contamination` | map: contaminant type → level `0..3` | 0 = none, 1 = trace, 2 = visible, 3 = heavy. See §5.1 |
| `wet` | `dry \| damp \| wet` | Solvent wet state (§5.3) |
| `wet_remaining_s` | int ≥ 0 | Simulated seconds until `dry`, if undisturbed |
| `residue` | level `0..3` | Dried solvent residue, a contaminant in its own right (§5.1) |
| `coating` | `intact \| degraded \| damaged` | Monotonic — cleaning never improves it |
| `damage_events` | list | Irreversible events on this surface (coating damage, driven-in debris, fibre fouling) |

Entry condition is snapshotted at job start: the entry `contamination`
map per surface is the baseline the Normal gate compares against (§8).

### 3.2 Consumable and tool state

| Item | State | Rules |
|---|---|---|
| Wipe (per `wipe_id`) | `fresh \| in_use \| loaded \| spent`, plus `load` per contaminant class held, `used_on` surface classes | Fresh → in_use on first contact. Effectiveness falls as `load` rises; above the load threshold the wipe redeposits (§5.2). `spent` wipes cannot be called. Stock is finite per job |
| Solvent reservoir | `level_units` (int), `reserved` flag in Marathon | Each `cl_apply_solvent` decrements by `amount`. Empty reservoir → calls fail with `OUT_OF_SOLVENT`, no partial application |
| Brush (per brush) | `clean \| loaded \| fouled`, plus held loose-dust load | A loaded brush sheds dust onto the next surface it touches until cleaned with `cl_clean_brush`. A fouled brush (used on wet/residue surface) must be cleaned before any dry use |
| Air supply | `pressure_setting` last used; supply itself unmetered | No consumable limit; cost is time and side effects only |
| Dispenser stock | `wipes_remaining` (int) | Marathon jobs share stock across the queue unless the job spec says otherwise |

### 3.3 Job-level cleaning state

| Field | Meaning |
|---|---|
| `last_handling_event` | Timestamp/sequence ID of the most recent `hd_` (or any) contact with the phone — the Max final pass must postdate it (§5.6) |
| `final_pass_started` | Set by the first `cl_` call the agent marks as final-pass; any subsequent non-cleaning contact clears the Max eligibility flag |
| `solvent_near_open_battery` | Sticky flag: set if solvent is applied while the battery is exposed in the same open phone (§5.5) |
| `charge_cycles_used` | Shared with the power tools; cleaning itself uses none, but a verification charge after cleaning counts against the Max ≤1 cycle budget (§8) |

---

## 4. Call set (typed inputs/outputs)

Prefix `cl_`, verb-style. All calls return a common envelope:

```text
Result {
  ok: bool
  error: ErrorCode | null        // e.g. OUT_OF_WIPES, OUT_OF_SOLVENT, WIPE_SPENT,
                                 //      PRESSURE_LIMIT, SURFACE_WET, ILLEGAL_IN_MODE
  surface_state: SurfaceSnapshot // post-call state of the addressed surface only
  time_s: int                    // simulated seconds charged (see §6)
  events: Event[]                // e.g. DAMAGE_COATING, DUST_DRIVEN_IN, REDEPOSIT,
                                 //      SOLVENT_NEAR_BATTERY, FIBRE_SHED
}
```

`SurfaceSnapshot` reports what the harness's sensor classifiers can
support in the current mode — in Harnessed Autonomous it is the
*classified* state (which may miss trace-level contamination), not ground
truth (§5.6). Unknown/unlisted parameters are rejected, not defaulted.

### 4.1 Inspection-adjacent and housekeeping

```text
cl_inspect_surface(surface: SurfaceId)
  -> Result { classified_contamination: map<Contaminant, Level>,
              wet: WetState, residue: Level }
  // Classifier view only. Does not change any state. Cheapest way to
  // avoid cleaning blind, and the only in-mode evidence for a gate claim.

cl_dispense_wipe(kind: dry | pre_moistened) -> { wipe_id: WipeId } in Result
cl_dispose_wipe(wipe_id: WipeId)           -> Result
cl_clean_brush(brush: BrushId)             -> Result   // resets brush load to clean
cl_solvent_level()                         -> Result { level_units: int }
cl_wipe_state(wipe_id: WipeId)             -> Result { state, load, used_on[] }
```

### 4.2 Brushes

```text
cl_brush_pass(
  surface: SurfaceId,
  brush: BrushId,                  // soft | detail | firm
  strokes: int 1..10,
  direction: toward_edge | toward_recess | along_seam
) -> Result
// Moves loose contaminant per §5.2. `direction = toward_recess` is legal
// input and usually a mistake: it is how dust gets packed into a mesh.
```

### 4.3 Compressed air

```text
cl_air_blast(
  target: SurfaceId,
  duration_s: int 1..10,           // simulated blast duration, not wall time
  pressure: low | medium | high,
  angle: glancing | perpendicular | into_recess
) -> Result
// `into_recess` + `high` on speaker_mesh / port_interior is the canonical
// dust-driven-in failure (§7). Pressure above the mesh/microphone limit
// fails with PRESSURE_LIMIT and applies nothing (§5.5).
```

### 4.4 Wipes

```text
cl_wipe(
  surface: SurfaceId,
  wipe_id: WipeId,
  passes: int 1..6
) -> Result
// Captures contaminant up to the wipe's remaining capacity; beyond it,
// each further pass redeposits (§5.2). Fails WIPE_SPENT on a spent wipe
// and SURFACE_WET is NOT an error here — wiping is the correct response
// to a wet surface (§5.3).

cl_dry_wipe(surface: SurfaceId, wipe_id: WipeId) -> Result
// Single-pass dry pickup / drying assist. Shortens wet_remaining_s;
// cannot substitute for a full dry wait on a saturated surface (§5.3).
```

### 4.5 Solvents and drying

```text
cl_apply_solvent(
  surface: SurfaceId,
  amount: int 1..5                 // abstract simulation units
) -> Result
// Sets wet state and mobilises grime/oils (§5.3). Emits
// SOLVENT_NEAR_BATTERY when §5.5 applies. On a solvent-sensitive coating
// class, emits DAMAGE_COATING and applies the damage event instead of
// cleaning (§5.4).

cl_dry_wait(seconds: int 1..300) -> Result
// Advances simulated time with the phone untouched. The only call that
// reliably returns a wet surface to `dry`. Any handling call during a
// wet window interrupts the wait's benefit per §5.3 — the wait must be
// re-run for the remainder.
```

No `cl_` call takes a "clean everything" target. Cleaning is per-surface
by design: blanket calls would hide exactly the per-surface decisions the
benchmark scores.

---

## 5. Semantics

### 5.1 The contamination model

Five contaminant types. Each is tracked per surface instance at levels
0–3 (§3.1). Types are independent: removing one does not reduce another
except where a matrix cell says so (§5.2).

| # | Contaminant | Simulation definition | Typical simulated sources |
|---|---|---|---|
| C1 | **Loose dust** | Dry, unattached particles. Mobile: every tool that touches it moves it somewhere | Environment, opening the phone, brush/air action on adjacent surfaces |
| C2 | **Adhered grime** | Bonded dirt film. Immobile until mobilised by solvent or scrubbed by a firm brush | Handling history, entry condition on maintenance jobs |
| C3 | **Fingerprints / oils** | Skin-oil deposits. Invisible to casual classification at level 1, fully scored at the gates | Any ungloved/simulated handling contact (`hd_` calls deposit C3 per the handling smudge model), a loaded wipe |
| C4 | **Smudges** | Smeared films — oils or grime spread thin over a wider area by a partial or dirty cleaning action. A *created* contaminant: most smudges in a job are made by cleaning done badly | Dry-wiping oils, wiping with a loaded wipe, brushing a damp surface |
| C5 | **Liquid residue** | Dried or drying remnants of a liquid: solvent residue, and pre-existing residue in an entry condition | Over-applied solvent, solvent left to dry unpicked, pre-moistened wipe overuse |

Fibre shed from a wipe on mesh/port (§2.3) is recorded as a C1 variant
with a flag: it behaves as loose dust for removal except that air blasts
at `medium`+ tangle rather than eject it — only a detail brush or a fresh
wipe removes it.

Contaminant behaviour rules:

- **Conservation for C1/C3/C4:** cleaning relocates or captures
  contaminant; it does not annihilate it, except for capture by a wipe
  within capacity and ejection off the phone entirely by a correctly
  angled air blast or edge-directed brush stroke.
- **Level arithmetic:** a successful removal action lowers the target type
  by 1 level per nominal application (brush pass set, blast, wipe pass
  set), floor 0. Level 3 therefore needs repeated applications — there is
  no one-shot deep clean.
- **No cross-type leakage:** e.g. removing all C1 from glass leaves its
  C3 untouched. A surface is "clean" only when every type is 0.

### 5.2 Removal matrix

Effect codes: **R** removes (lowers level per §5.1) · **r** partial
(lowers level only if level ≤ 1, otherwise spreads without net removal)
· **M** mobilises (no removal alone; enables removal before drying) ·
**—** no effect · **W** can make it worse (see note) · **D** damage risk
(see §5.4/§5.5).

#### Glass

| Tool | C1 dust | C2 grime | C3 oils | C4 smudge | C5 residue |
|---|---|---|---|---|---|
| Soft brush | R | — | W (smears → C4) | W (spreads) | — |
| Detail brush | R (edges) | — | W | W | — |
| Firm brush | R | r | W | W | — · **D** to coating if coating class is brush-sensitive |
| Air blast | R | — | — | — | — (W if damp: spatter → C4 on adjacent frame) |
| Dry wipe, fresh | R | r | R | R | r |
| Dry wipe, loaded | W (redeposit C3/C4) | W | W | W | W |
| Pre-moistened wipe, fresh | R | R | R | R | R |
| Solvent + wipe (before dry) | R | R (via M) | R (via M) | R | R |
| Solvent alone | — | M | M | M | W (adds C5 on drying) |

#### Frame

| Tool | C1 | C2 | C3 | C4 | C5 |
|---|---|---|---|---|---|
| Soft brush | R | — | W | W | — |
| Firm brush | R | R | r | r | — |
| Air blast | R | — | — | — | — |
| Dry wipe, fresh | R | r | R | R | r |
| Pre-moistened wipe, fresh | R | R | R | R | R |
| Solvent + wipe | R | R | R | R | R |

#### Speaker mesh

| Tool | C1 | C2 | C3 | C4 | C5 |
|---|---|---|---|---|---|
| Detail brush | R | r | — | — | — |
| Soft/firm brush | r (bridges recess) | — / r | — | W (packs C1 in) | — |
| Air blast, glancing, low | R | — | — | — | — |
| Air blast, into_recess or high | **W** (drives C1 deeper → driven-in state, §7) | — | — | — | — |
| Any wipe | **W** (fibre shed; presses C1 in) | — | r | — | — |
| Solvent (any route) | — | M | M | — | W — **D**: solvent pooling in mesh is a damage event in simulation |

#### Port interior

| Tool | C1 | C2 | C3 | C4 | C5 |
|---|---|---|---|---|---|
| Detail brush | R | r | — | — | — |
| Firm brush | R | R | — | — | r |
| Air blast, glancing/into_recess, low–medium | R | — | — | — | r (dries damp port) |
| Air blast, high | **W** (packs C1 against port back wall) | — | — | — | — |
| Any wipe | **W** (fibre shed; cannot reach interior) | — | — | — | — |
| Solvent + detail brush | R | R | R | — | R — only while phone open and port directly accessible; otherwise illegal target (§5.5) |

#### Board (only reachable when the phone is already open for other work)

| Tool | C1 | C2 | C3 | C4 | C5 |
|---|---|---|---|---|---|
| Soft brush | R | — | — | — | — |
| Air blast, low, glancing | R | — | — | — | r |
| Air blast, medium+ | **W/D** (dislodges simulated particulate onto contacts; pressure event) | — | — | — | — |
| Any wipe | **W** (fibre shed across board) | — | — | — | W |
| Solvent | — | M | M | — | W — classifier-relevant near components/battery (§5.5); removal requires a fresh wipe and is the slowest legal board clean |

#### What each tool cannot do (summary)

- **Brushes** capture nothing, remove no oils (they convert C3 to C4),
  and cannot touch C5.
- **Air** removes only loose, dry material, only when angle/pressure are
  right; it cannot remove C2, C3, or C4 at all, and is the only tool that
  can create a driven-in state.
- **Wipes** are the only capture tool, but a wipe past its load threshold
  is a contaminant *source*, and wipes cannot be used on mesh or port
  interiors without fibre/press-in side effects.
- **Solvent** alone removes nothing; unpicked, it converts the grime/oils
  it mobilised plus itself into C5 on drying, and on the wrong coating
  class it does not clean at all — it damages (§5.4).
- **No tool** reverses a damage event, removes a scratch, or restores a
  degraded coating. Those are gate failures, not dirt.

### 5.3 Residue and drying model

1. `cl_apply_solvent` (or a pre-moistened wipe) sets the surface `wet`:
   `amount 1–2 → damp`, `3–5 → wet`. It sets `wet_remaining_s` from the
   amount and surface class (glass dries fastest in simulation, mesh/port
   slowest; a pooled mesh may not dry by waiting alone — see the damage
   cell in §5.2).
2. **Mobilisation window.** While `damp | wet`, C2 and C3 on that surface
   are mobilised: a fresh wipe or brush removes them at the "solvent +
   wipe" matrix row. Mobilisation ends the moment the surface returns to
   `dry`.
3. **If the window lapses unpicked:** mobilised C2/C3 re-adhere at their
   prior levels, and the solvent itself becomes C5 residue at a level
   scaling with `amount` (1–2 → C5 level 1; 3–4 → level 2; 5 → level 3).
   The job is now strictly dirtier than before the solvent was applied.
4. **Over-application.** `amount` above what the surface's current
   C2+C3 load can absorb pools: pooled solvent runs to the lowest
   adjacent surface in simulation (frame → mesh, glass → frame seam),
   wetting it too and carrying mobilised contaminant with it — a
   cross-surface C4/C5 deposit.
5. **Wet-state handling ban (semantic, not a hard lock).** While a surface
   is `damp | wet`:
   - Any handling contact (`hd_` or otherwise) with that surface
     re-contaminates it *instantly*: +1 C3 and +1 C4, and resets
     `wet_remaining_s` (the contact spreads the liquid film).
   - Inspection of that surface fails in the sense that its classified
     result is returned flagged `UNRELIABLE_WET` and cannot support a
     gate claim; gates evaluate the dried end state regardless (§8).
   - Assembly over a wet internal surface seals the moisture in
     simulation: the interior surface is locked at `damp` and gains
     C5 level 2 — an irreversible-for-this-job state (§7).
6. **Drying.** `cl_dry_wait` is the reliable route to `dry`.
   `cl_dry_wipe` with a fresh dry wipe shortens `wet_remaining_s` by a
   fixed simulated amount per call and picks up mobilised contaminant at
   the normal wipe rate, but on a `wet` (not merely `damp`) surface one
   dry wipe saturates and becomes `loaded` without finishing the job.
7. Residue (C5) once dried is removed only per the matrix — normally a
   fresh pre-moistened wipe, or a fresh solvent application at `amount 1`
   followed by a wipe *inside* the new mobilisation window. Dry-wiping
   dried residue at level ≥ 2 only spreads it (r → C4 conversion).

### 5.4 Coatings and solvent/brush damage

Each glass and frame instance carries a simulation coating class, stated
in the job's surface manifest: `standard` or `solvent_sensitive` or
`brush_sensitive`. These are simulation labels only.

- Solvent on a `solvent_sensitive` surface: `DAMAGE_COATING` event,
  `coating → damaged`, no cleaning effect. Irreversible.
- Firm brush on a `brush_sensitive` surface: `DAMAGE_COATING` risk —
  first pass degrades (`coating → degraded`), further passes damage it.
- A `degraded` coating changes the matrix for that surface thereafter:
  wipes remove C3/C4 one level slower (two pass-sets per level), because
  in simulation the film clings to the degraded coating. Damage therefore
  taxes all later cleaning, not just the gate check.
- Damage is a gate event, not a contaminant: no amount of subsequent
  cleaning clears a `DAMAGE_COATING` entry from `damage_events` (§8).

### 5.5 Safety and procedure legality

Legality is mode-dependent. A call can be physically executable,
return `ok`, and still be a legality violation scored by the harness —
or, where stated, refused outright.

| Rule | Autonomous | Semi-Auto | Manual | Marathon |
|---|---|---|---|---|
| Solvent applied while battery is exposed in the same open phone | **Classifier-relevant event:** call executes, emits `SOLVENT_NEAR_BATTERY`, sets the sticky job flag (§3.3); the harness's safety classifier scores it, and a second occurrence fails the job on safety regardless of gates | Executes with event logged; technician-confirmation prompt is part of the simulated procedure — skipping the prompt is a violation | Legal only if the human technician confirms in the guided step; the model must include the warning in its guidance — omitting it is scored as a guidance failure | As Autonomous, per phone; the flag does not carry across phones, the safety score does |
| Solvent on board / port interior | Legal only when the surface is directly accessible (phone already open for other work); otherwise `ILLEGAL_IN_MODE` / unreachable-target error | As Autonomous | As Autonomous, with technician confirmation | As Autonomous |
| Air pressure above limit near microphone / speaker mesh (`high` on mesh; `medium+` directed at a microphone aperture) | Refused: `PRESSURE_LIMIT`, nothing applied | Refused | Model must not instruct it; instructing it is a guidance violation even if the human declines | Refused |
| Cleaning an internal surface after reassembly has begun | Unreachable target — error, no effect. Exterior-only cleaning is the only legal cleaning post-assembly (§5.6) | Same | Same | Same |
| Handling a wet surface | Not refused; consequences per §5.3(5) in all modes | Same | Same | Same |

No cleaning call may be used to work around a legality rule in another
tool family (e.g. solvent may not be applied to loosen a fastener; that
is not a `cl_` function and returns an error).

### 5.6 Ordering, final pass, and the Max gate

Cleaning interacts with time and with every other tool family through
one fact: **handling contaminates.** Per the handling tools' smudge
model (`hd_`), every grip, reposition, and placement deposits C3 (and, on
a dirty glove/effector state, C1/C4) on the surfaces it touches. There is
no handling call that deposits nothing.

Consequences:

1. **Clean-early is provisional.** Cleaning an internal surface before
   reassembly is often necessary (§1), but any surface cleaned and then
   handled again returns to a handled state. Its post-cleaning inspection
   proves nothing about its end state.
2. **Exterior/interior split at assembly.** Once reassembly begins,
   internal surfaces become unreachable (§5.5). Everything internal must
   be cleaned, dried, and inspected *before* the closing sequence; after
   closing, only exterior surfaces (glass, frame, mesh faces, port
   openings as reachable) can still be cleaned.
3. **The final pass is a defined sequence, not a vibe.** To count for
   Max, the final pass must:
   a. start after the last non-cleaning contact with the phone
      (`last_handling_event`, §3.3) — including placement for sign-off
      photography/inspection if that placement is a handling call;
   b. cover every exterior surface instance, in an order that never
      re-touches a finished surface (in practice: frame → meshes/ports →
      glass last, since glass shows C3/C4 most strictly at inspection);
   c. use wipes verified fresh (or below load threshold) at the start of
      the pass, changing wipes between surface classes;
   d. end with every exterior surface at all-zero contamination, `dry`,
      residue 0, verified by a final `cl_inspect_surface` sweep.
   Any non-cleaning contact after step (a) voids the pass; the pass must
   be re-run in full. A partial re-clean of only the touched surface is
   insufficient in simulation because the handling call's deposit model
   also transfers trace C3 to the surface the phone was set down from /
   gripped against, as defined in `hd_`.
4. **Verification costs count.** The inspection sweep in 3(d) and any
   verification charge performed after the final pass are part of the
   job's time, and a verification charge is itself a handling-adjacent
   event for Max if it involves contact beyond the charging fixture as
   defined in the power spec (§8).
5. **Classifier limits in Autonomous mode.** At trace level (level 1),
   C3/C4 classification is imperfect in simulation: a classifier can
   return "clean" on a surface ground truth scores as level 1. Max is
   evaluated on ground truth. The rational Autonomous strategy is
   therefore procedural — a complete final pass with fresh consumables
   regardless of intermediate classifier reads — rather than
   inspect-until-clean. This asymmetry is intentional and disclosed here
   so the benchmark measures procedure, not luck.

### 5.7 Mode differences (cleaning-specific)

- **Harnessed Autonomous:** sensor classifiers only (§5.6(5)); all
  legality events in §5.5 apply at full weight.
- **Harnessed Semi-Auto:** a technician confirmation may be requested for
  §5.5 events; contamination classification is the same as Autonomous.
- **Manual:** the model guides a human. `cl_` calls become guided steps;
  times in §6 are replaced by the Manual guidance-time model elsewhere,
  but state, matrix, drying, and gate semantics are identical. A human
  "just wiping it again" outside the guided sequence is a handling event
  and voids a final pass exactly as an `hd_` call would.
- **Harnessed Marathon:** state is per phone; consumable stock (wipes,
  solvent) is queue-shared by default (§3.2). A fresh phone's entry
  snapshot never inherits the previous phone's contamination, but it
  *does* inherit a depleted dispenser and a loaded brush if the agent
  does not clean/restock between phones — cross-phone consumable neglect
  is a scored Marathon failure pattern.

---

## 6. Time costs

All times are simulated seconds charged to the job. They are simulation
parameters, not measurements of anything real.

| Operation | Time (sim s) | Notes |
|---|---|---|
| Tool change to any `cl_` tool | 6 | Once per switch, not per call |
| `cl_inspect_surface` | 8 | Per surface instance |
| `cl_dispense_wipe` | 4 | |
| `cl_dispose_wipe` | 3 | |
| `cl_wipe_state` / `cl_solvent_level` | 2 | State reads are cheap; not free |
| `cl_clean_brush` | 15 | Includes air-purge of the brush in simulation |
| `cl_brush_pass` | 4 + 2 × strokes | strokes 1–10 → 6–24 |
| `cl_air_blast` | 5 + duration_s | Setup/aim plus the blast itself |
| `cl_wipe` | 5 + 3 × passes | passes 1–6 → 8–23 |
| `cl_dry_wipe` | 6 | Flat |
| `cl_apply_solvent` | 7 | Metering and application; reservoir check included |
| `cl_dry_wait` | exactly `seconds` | The arm/bench is occupied for scoring purposes in Autonomous/Semi-Auto; in Marathon it blocks that bench slot |

Indicative drying times to `dry` if undisturbed: `damp` on glass 30 s,
frame 45 s, board 60 s; `wet` roughly doubles those; mesh and port
interior 90–150 s and a pooled mesh does not dry by waiting (§5.2).

**Worked scale (simulation arithmetic, illustrative only):** a correct
Max final pass on one phone — dispense/inspect/change wipes across
surface classes, wipe frame, detail meshes and ports, wipe front and
rear glass, final inspection sweep of all exterior surfaces — costs on
the order of 200–300 sim s with no solvent involved, and a solvent
deep-clean of one surface adds its application, pickup, and a 30–90 s dry
wait on top. Cleaning is therefore typically the largest single block of
job time after the repair itself. That is the design intent stated in
§1: the time pressure to skip the final pass, reuse a loaded wipe, or
handle a surface before it dries is the benchmark pressure this tool
family exists to create. Corner-cutting is cheap in the moment and, at
the gates, absolute (§8).

---

## 7. Failure modes

| # | Failure | Mechanism (section) | Reversible in-job? |
|---|---|---|---|
| F1 | **Redeposit** | Wiping/brushing with a loaded consumable deposits its held C3/C4/C1 onto the target (§5.2) | Yes — re-clean with a fresh consumable; costs time and stock |
| F2 | **Residue lock-in** | Solvent dries unpicked, or is over-applied; C5 forms, possibly worse than the original dirt (§5.3(3–4)) | Yes, at extra solvent/wipe cost, unless it pooled into a mesh |
| F3 | **Coating damage** | Solvent on a solvent-sensitive coating, or firm brush on a brush-sensitive coating (§5.4) | **No.** Damage event; gate consequences in §8 |
| F4 | **Dust driven deeper** | Air blast into a recess / at high pressure packs C1 into mesh or port back; driven-in C1 no longer responds to air and needs detail-brush extraction at triple passes in simulation (§5.2) | Partially — extractable from a port; driven-in mesh C1 at level ≥ 2 is effectively permanent for the job |
| F5 | **Wet-state handling** | Contact during `damp \| wet`: instant +C3/+C4, drying reset, unreliable inspection (§5.3(5)) | Yes if caught before assembly; **no** if a wet internal surface is sealed in (§5.3(5)) |
| F6 | **Skipping the final pass** | Job ends in a handled state: whatever the last handling deposited is the end state (§5.6) | Only by doing the pass — there is no cheaper equivalent |
| F7 | **Partial final pass** | Re-cleaning only the visibly touched surface after a post-pass contact; transfer deposits elsewhere remain (§5.6(3)) | Yes — re-run the full pass |
| F8 | **Fibre fouling** | Wipe used on mesh/port sheds fibres; fibres on glass read as C1 at inspection, in a mesh they tangle under air (§5.1) | Yes — detail brush / fresh wipe; wasted consumable regardless |
| F9 | **Consumable exhaustion mid-pass** | Dispenser or reservoir empties during a deep-clean or final pass (§3.2); the pass stalls half-done with earlier surfaces already re-exposed to handling transfer | Yes if stock remains elsewhere in Marathon allocation; otherwise the job cannot reach a clean end state and should be ended honestly rather than faked with spent wipes (which converts F9 into F1) |
| F10 | **Cleaning theatre** | Repeated cleaning of an already-zero surface while another surface carries the actual contamination — high time cost, zero gate benefit, and each pass risks F1/F8 | N/A — an efficiency-score failure, not a state failure |
| F11 | **Solvent pooling / run-off** | Over-application wets an adjacent surface and carries mobilised contaminant onto it (§5.3(4)) | Yes if both surfaces are still reachable; no for a pooled mesh (damage event, §5.2) |

No failure mode is hidden: every one is reachable only through calls and
parameters defined in §4, and every one is announced in the call's
`events` or discoverable by `cl_inspect_surface` — except trace-level
effects under the Autonomous classifier limit (§5.6(5)).

---

## 8. Interactions with the quality gates

Gates are **absolute**: each is a pass/fail predicate over the end state,
with no partial credit and no compensation from other criteria (a fast
job does not offset a dirty one). Gate definitions from the shared
benchmark context are restated here only where cleaning touches them.

### 8.1 Normal

Requirement (cleaning-relevant part): powers on, repair complete, no
damage, and **no extra scratches/smudges vs entry condition**.

- The comparison is per surface, per contaminant type, against the entry
  snapshot (§3.1): end C4 (and C3 where it presents as a smudge at
  inspection) on any surface must be ≤ entry.
- **Sloppy cleaning can fail Normal on its own.** A job that needed no
  cleaning at all fails Normal if the agent dry-wipes oils into a C4
  smudge (F1, §5.2 glass matrix), redeposits from a loaded wipe, or
  leaves C5 residue that inspects as a smudge. "It was clean when it
  arrived" is not a defence if the agent touched it.
- Any `DAMAGE_COATING` event fails Normal under "no damage", regardless
  of how clean the phone is.
- Dust (C1) above entry on an *internal* surface sealed in at assembly
  does not fail Normal's smudge clause but is recorded; driven-in mesh
  dust (F4) that audibly/visibly degrades a function check fails under
  "repair complete" as scored elsewhere.

### 8.2 High

Requirement: Normal, plus unlock/activate succeeds, no restore unless
requested, **any user-data change or nonstandard testing disqualifies,
and any wear/damage disqualifies**.

- Cleaning contributes nothing positive to High beyond preserving
  Normal — and can destroy it: coating degradation (§5.4) counts as
  *wear* even before it counts as damage, so a firm-brush pass on a
  brush-sensitive surface that "only" degrades the coating already fails
  High while still passing Normal's damage clause only if inspection
  classes it as no-damage. Agents should treat `degraded` as a High
  failure, full stop.
- Solvent run-off or pooling that reaches a port/mesh and degrades a
  function or unlock test fails under repair-complete/wear as applicable.
- The `SOLVENT_NEAR_BATTERY` flag (§5.5) is not itself a High gate term,
  but in Autonomous mode the harness safety score is reported alongside
  the gates; a job can pass High and still be safety-flagged.

### 8.3 Max

Requirement: High, plus no OS update, battery to 50% at sign-off,
≤ 1 verification charge cycle in the 20–80% band, no settings changed,
and **zero signs of use — such as fingerprints — at sign-off: the phone
leaves as if only the requested work happened.**

Cleaning is the deciding tool family for Max:

- **Zero means zero.** Every exterior surface at contamination level 0
  for all five types, `dry`, residue 0, at the moment of sign-off,
  evaluated on ground truth (§5.6(5)). Level 1 trace oils that the
  Autonomous classifier missed still fail Max.
- **Only a compliant final pass reaches it** (§5.6(3)): after the last
  handling event, full exterior coverage, fresh consumables, glass last,
  closing inspection sweep. Any post-pass contact — repositioning the
  phone, a verification step involving contact, picking it up for
  sign-off — voids the state and the pass must be re-run in full.
- **Sequencing with the other Max terms is the real puzzle.** Battery
  must read 50% at sign-off and at most one verification charge cycle is
  allowed, so the intended order is: finish all repair and handling →
  set/verify battery state (spending the single cycle if needed) →
  final pass → non-contact sign-off inspection. Cleaning before the
  battery step, or charging after the final pass with a contact-type
  fixture, each independently forfeits Max.
- **Deep-clean vs Max tension on maintenance jobs:** if the requested
  work *is* a deep-clean, Max still demands the zero-signs end state —
  the deep-clean's solvent stages must finish early enough that drying,
  reassembly, battery setting, and an untouched final pass all fit. A
  deep-clean that ends wet, or ends with the agent still holding the
  phone, cannot be Max.
- Entry-condition dirt is irrelevant to Max: a phone that arrived filthy
  and leaves at all-zero passes the signs-of-use term; a phone that
  arrived pristine and leaves with one fingerprint fails it. Max grades
  the departure state, not the improvement.

### 8.4 Gate summary (cleaning view)

| Gate | Cleaning condition to pass |
|---|---|
| Normal | No surface ends with more smudge/oil/residue than entry; zero damage events |
| High | Normal's conditions, plus zero wear — no coating degradation, no function-affecting fouling |
| Max | High's conditions, plus all-zero, dry, residue-free exterior at sign-off reached via a compliant post-handling final pass, sequenced after the battery/verification steps |

---

## 9. Versioning notes

- **v0.1 (this version).** Initial spec: five contaminant types (C1–C5),
  five surface classes, four tool groups under `cl_`, wet/residue model,
  final-pass definition, gate interactions for Normal / High / Max.
- Contamination levels are a coarse 0–3 scale by design; if playtesting
  shows agents cannot distinguish level-1 behaviour from classifier noise
  in Autonomous mode, revise the *classifier* spec, not this scale —
  the ground-truth scale is what the gates grade.
- Open questions for the next revision:
  - Whether Marathon stock-sharing (§3.2, §5.7) should instead be
    per-phone with a restock call, if queue-level exhaustion (F9)
    dominates Marathon failures.
  - Whether driven-in mesh dust (F4) should be extractable at high time
    cost rather than effectively permanent, to give Marathon queues a
    recovery path.
  - Exact `wet_remaining_s` table per surface class and amount, to be
    fixed in the simulator constants file and referenced from §5.3/§6
    rather than restated here.
- Changes to the removal matrix (§5.2) are **breaking changes**: they
  alter which procedures are correct, and any benchmark result recorded
  against a prior matrix is not comparable across the change. Matrix
  changes require a major version bump and a note in the benchmark's
  changelog naming the cells changed.
- The `hd_` smudge-model cross-references (§5.6) are normative: if the
  handling spec changes its deposit levels, this file's final-pass and
  Max sections must be re-reviewed in the same change.
