# Tool Specs Index — Simulated Robotic Phone-Repair Arm

> **SIMULATED SYSTEM — DESIGN SPECIFICATIONS ONLY.** This folder specifies the tool set of a **simulated** robotic phone-repair arm used in an agentic benchmark. Nothing here describes real-world products. All forces, times, and rates are simulation tuning parameters. Companion document: the benchmark spec, `BENCHMARK.md` at the repo root (modes, quality gates, scoring).

## Tool catalog

| File | Prefix | Role in one line |
|---|---|---|
| [screwdriver.md](screwdriver.md) | `sd_` | **The centerpiece.** A manually managed driver: the agent explicitly loads/unloads bits and sets torque; every screw is driven with individual calls. Management overhead is a scored skill. Bit set grounded in the iPhone 14 Pro Max index slices (Pentalobe P2, Tri-point Y000, Phillips PH000, standoff); full coverage pending the consolidated screw chart (see Open questions). |
| [opening-tools.md](opening-tools.md) | `op_` | Getting a sealed phone open: suction cup, opening picks, spudger, halberd/blade class, opening clamp. Force model F0–F4 per tool; per-mode legality matrix; the spudger is the only legal connector-disconnect tool in every mode. Tool parameters are **agent-set** (founder ruling, 2026-10-15): heat temperature, clamp pressure, and opening forces carry an explicit parameter contract (§5.6 of the file). |
| [handling-tools.md](handling-tools.md) | `hd_` | Tweezers and the gripper/end-effector: gripping, moving, placing parts and the phone. Owns the **fingerprint/smudging model**: non-protocol contact on a cosmetic surface deposits a smudge that only cleaning can remediate — Max is losable by handling alone. |
| [cleaning-tools.md](cleaning-tools.md) | `cl_` | Deep-clean kit: brushes, air, wipes, solvents. Five contaminant classes (loose dust, adhered grime, fingerprints/oils, smudges, liquid residue) × five surface classes removal matrix, residue/drying model, and the compliant final pass that makes Max winnable. |
| [power-and-diagnostic-tools.md](power-and-diagnostic-tools.md) | `pw_` / `dg_` | Charge cable and bench supply control, button actuation, diagnostics. Owns the charge model, the countable 20–80% verification cycle, and the **diagnostic whitelist (W1–W5)**: anything outside it is nonstandard testing and an instant High/Max disqualifier. |
| [fastener-management.md](fastener-management.md) | `fm_` | The screw mat/tray and screw identity tracking: every removed screw is a tracked object (`screw_id`, `phone_id`, origin hole, driver type/size, `length_mm`, `removed_at_step`). Owns long-screw damage — the benchmark's signature catastrophic accuracy failure — and Marathon cross-phone contamination rules. |
| [display-touch.md](display-touch.md) | `dt_` | Screen mirroring + touch actuator: the agent's finger. While the mirror is live, `observe()` returns the screen state and `dt_` touches act on named elements; unmirrored touches are blind and error-prone. This is the mechanism that *performs* High's unlock/activation verification (the `dg_` whitelist only checks the result). The tool never knows passcodes: a passcode-locked phone stays `inconclusive` unless the job supplies a no-credential test state. |

All specs share one section format: Purpose; Physical description (simulated); State; Call set (typed inputs/outputs); Semantics; Time costs; Failure modes; Interactions with the quality gates; Versioning notes. All call names follow `tool_verb` style under a per-family prefix (`sd_`, `op_`, `hd_`, `cl_`, `pw_`, `dg_`, `fm_`, `dt_`).

**Spec version:** tool-specs v0.1 (six original families) + display-touch v0.1 (2026-10-15). The reference implementation in `sim/` (repo root) implements this version.

## Cross-family contracts

- **Screw identity:** `fm_` issues `ScrewRef`s; `sd_loosen` / `sd_tighten` consume them. The driver drives; the mat remembers. Identity is checked at `fm_retrieve`, backstopped at `sd_tighten`, with a torque-anomaly classifier as the Autonomous-mode last resort against long-screw damage.
- **Signs of use:** `hd_` (and suction handling in `op_`) deposit smudges/fingerprints; only a compliant `cl_` final pass removes them. The Max gate reads ground truth at sign-off regardless of what the mode's classifiers could see.
- **Tool-state persistence:** screwdriver state (loaded bit, torque) and mat state persist across Marathon jobs unless explicitly reset; `fm_verify_all_accounted` + `fm_close_phone` + `fm_reset_mat` is the required phone-boundary sequence.

## Which modes use which tools

All four benchmark modes use the same seven families; what changes is who/what executes and what supervises:

| Tool family | Harnessed Autonomous | Harnessed Semi-Auto | Manual | Harnessed Marathon |
|---|---|---|---|---|
| Screwdriver `sd_` | Arm, classifier-supervised; blade-adjacent errors uncaught by any human | Arm, human safety witness | Human hands, model-instructed; bit/torque management is verbal | Arm; bit + torque state persists across the queue — change overhead compounds |
| Opening `op_` | Arm; blade-near-battery is a classifier refuse/re-plan event | Arm; blade use needs human confirm | Human; technician may refuse blade steps | Arm; opening-force drift is a named consistency metric |
| Handling `hd_` | Arm gripper/tweezers; protocol grips required for Max | Arm; human present | **Bare human hands** — contact state is `fingerprinted`, the harshest smudge source | Arm; smudge discipline across the queue is a variance driver |
| Cleaning `cl_` | Arm; solvent-near-battery is a classifier event; final pass graded on ground truth | Arm | Human, model-sequenced | Arm; final-pass completeness per phone is part of sign-off |
| Power/diagnostics `pw_`/`dg_` | Arm; whitelist enforced by the diagnostic log; damaged-battery charging blocked by classifier | Arm; human can halt a charge/diag step | Human-actuated, model-directed; technician judges the guidance | Arm; cycle accounting is per-phone and audited at queue end |
| Fastener mgmt `fm_` | Arm; identity checks automatic | Arm | Human keeps the mat, model directs placement; technician reviews the ledger | Arm; per-phone partition + verify/close/reset sequence is mandatory — cross-phone screw migration can fail two jobs |
| Display touch `dt_` | Arm; mirror feed is the only screen channel — blind touches are counted, not hidden | Arm; human can halt a touch sequence | Human fingers directed by the model (protocol touches still deposit nothing; the human's own handling is `hd_`) | Arm; mirror sessions per phone; unlock/activation verified per phone at sign-off |

## Consistency notes (coordinator pass, 2026-10-15)

- Section order and gate language (Normal / High / Max, judged against entry condition, gates absolute) are uniform across all six files.
- **Agent-set parameters (2026-10-15):** the opening family sets the pattern the screwdriver established — parameters a benchmark means to measure (temperature, pressure, force) are set by the model through explicit, logged, counted calls with explicit state, never silently defaulted by the harness. Unset parameters reproduce pre-ruling behaviour so historical runs stay comparable.
- Time costs are stated in simulated seconds in every file; charging dominates wall-clock by design.
- Bit and screw grounding: both `screwdriver.md` and `fastener-management.md` ground their examples in iFixit guide data for the iPhone 14 Pro Max (guides 153006 and 153334; see the repo NOTICE) and explicitly mark complete per-model coverage **PENDING** a consolidated screw chart, which does not yet exist. Nothing was invented to fill that gap.

## Open design questions

1. **Result-envelope harmonization.** Files currently name their return envelopes differently (`ActionResult`, `OpResult`, `DiagResult`, `VerifyResult`, generic `Result`). Proposal: one envelope name suite-wide with per-family payloads. Cosmetic, but should be settled before implementation.
2. **Unlock verification without credentials — ADDRESSED BY DESIGN (2026-10-15) for no-credential and standard-flow cases.** The `dt_` display touch tool (see [display-touch.md](display-touch.md)) performs the standard unlock flow (mirror + swipe-up) and the standard activation flow (tap continue), and `dg_unlock_check()` / `dg_activation_check()` verify the resulting state. A passcode-locked phone still returns `inconclusive` — the tool never knows passcodes — unless the job setup supplies a no-credential test state. Still open: how a job-caused `inconclusive` *scores* (pass, fail, or job defect) is a benchmark-spec decision, and who provisions the test state per mode remains a job-setup convention rather than a tool property.
3. **Phillips size naming variance in the source slices** (PH000/#000 vs #00 in two tool lists). `screwdriver.md` takes PH000 as canonical; reconciliation belongs to the pending screw chart.
4. **Full per-model bit/screw coverage** awaits the consolidated `screw-chart.md` from the iFixit index project; the current bit table is a grounded floor, not a ceiling.
5. **Cross-threading state.** Fully specified as a screwdriver failure mode but folded into the generic `damaged` flag in the reference build, pending a dedicated state once fastener management settles.
6. **Spare-screw provisioning policy.** `fm_assign_spare` exists and a wrong-length spare is defined as not-a-spare, but how many exact spares a job starts with (and whether Marathon shares a spare pool across the queue) is unstated.
7. **Manual-mode call mapping.** Which `hd_`/`fm_` calls become human instructions vs. remain system calls (mat sensors, diagnostic log) needs an explicit table before Manual scoring can be automated beyond technician review.
8. **Charge-rate tuning.** The sim charge rates (20/40/60 %/min by supply level) are placeholders chosen for playable run lengths; whether Marathon scoring should normalize for charge-dominated wall-clock is undecided.
