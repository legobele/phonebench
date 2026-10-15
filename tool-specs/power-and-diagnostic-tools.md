# Power and Diagnostic Tools — Design Spec

> **SIMULATED SYSTEM — DESIGN SPECIFICATION ONLY**
>
> This document specifies tools for a *simulated* robotic phone-repair arm
> benchmark. Every device, supply, cable, actuator, rate, voltage/current
> label, and behaviour described here is a simulation parameter chosen for
> the benchmark. Nothing in this file is a claim about any real-world
> product, charger, phone, diagnostic service, or repair procedure, and no
> value here should be carried over to work on real hardware.

| Field | Value |
|---|---|
| Tool group | Power supply / charging, power-button actuation, diagnostics |
| Call prefixes | `pw_` (power), `dg_` (diagnostics) |
| Applies to modes | Harnessed Autonomous, Harnessed Semi-Auto, Manual, Harnessed Marathon |
| Scored on | Time, efficiency, accuracy — subject to the absolute quality gates in §8 |
| Status | v0.1 draft (see §9, Versioning notes) |

---

## 1. Purpose

This tool group gives the controlling model three capabilities, and only
three:

1. **Energy delivery** — connect/disconnect a simulated charge cable,
   control a simulated bench power supply, and charge the device under a
   deterministic charge model (§5.2), including the single countable
   20%→80% battery verification cycle the Max gate allows (§5.3).
2. **Power-state control** — actuate the device's power button (and
   standard button combinations), power the device on and off, and *query*
   the resulting power state. Power-on, unlock, and activation are three
   distinct proofs, for three distinct gate tiers (§5.4).
3. **Diagnostics** — run a closed, whitelisted set of read-only diagnostic
   techniques (§5.5) and read back their results. Diagnostics are the
   highest-risk capability in this group: a diagnostic action outside the
   whitelist is not a style error, it is an instant disqualifier at High
   and above and raises a user-data-change audit flag.

The tool group exists so a job can be *verified*, not merely *finished*.
A repair that cannot be powered on, unlocked, activated, and (at Max)
charge-verified inside these rules is not complete, however fast it was.

Non-goals:

- This toolset is **not** a general device-management interface. It has no
  calls for browsing user content, opening apps, enrolling accounts,
  pairing accessories, or configuring the device.
- It is **not** a software-servicing toolset. Restore and update are
  *physically possible* through the bench supply + cable (§5.6) but are
  gate-fatal levers, specified here only so the sim can model, log, and
  judge their accidental or deliberate use.
- It does **not** give the arm any credential capability. The arm can
  actuate buttons and observe screen state; it cannot enter a user's
  passcode (see §5.4 and the open question there).

Mode differences for this tool group:

| Mode | Who/what authorises a `pw_`/`dg_` call | Extra rule |
|---|---|---|
| Harnessed Autonomous | The model; sensor classifiers only | The safety classifier is the only safety net. A classifier event (e.g. charge attempted on a known-damaged battery, power-on into a shorted board) is recorded as a safety event and the call is blocked, not merely warned (§7). |
| Harnessed Semi-Auto | The model, with a supervisor who can halt flagged calls | Classifier `flag` verdicts are surfaced to the supervisor before execution; `block` verdicts do not execute. |
| Manual | The model guides a human technician; results are technician-reviewed | A human performs/attests physical steps (cable seating, button presses, screen observations). Human attestation does **not** widen the diagnostic whitelist and does not waive any gate. |
| Harnessed Marathon | The model, per phone, across a queue | All state in §3 — cable, supply, charge session, verification-cycle count — is **per-phone** and resets at phone handover. A cycle or charge session must never carry over from one queued phone to the next. |

---

## 2. Physical description (simulated)

All of the following are simulated bench objects. The arm interacts with
them only through the calls in §4.

### 2.1 Bench power supply

- A simulated bench supply with a controllable output: on/off, plus a
  named output level from a closed set (`"off"`, `"trickle"`,
  `"standard"`, `"high"`). Levels are sim labels that select a charge
  rate (§5.2); they are not real voltages or currents.
- The supply reports its own state (on/off, level, whether current is
  being drawn) as bench telemetry. Bench telemetry is sim-generated and
  read-only to the model.
- The supply can, in principle, deliver enough energy and data-path
  control to push a restore or an OS update over the cable (§5.6). That
  capability is part of the simulated hardware; using it is a gate
  decision, not a hardware limitation.
- Default at job start: supply **off**, no cable connected.

### 2.2 Charge cable

- One simulated charge/data cable between the bench supply (or bench
  data port) and the device's charge port.
- Connected/disconnected is a discrete, observable state (§3). Connection
  and disconnection are deliberate arm actions (`pw_connect_cable()` /
  `pw_disconnect_cable()`), each with a time cost (§6) and each a
  *handling event*: like other physical handling in the sim, handling the
  device to seat or remove the cable can leave a fingerprint unless the
  final cleaning step removes it — which matters at Max (§8).
- The cable is the only energy/data path this tool group provides.
  Charging is impossible with the cable disconnected or the supply off;
  diagnostics that need the device powered follow §5.5's own rules.

### 2.3 Button actuators

- A simulated button actuator (a small presser driven by the arm) that
  can press the device's power button, and — in combination — the other
  physical buttons the sim models (`"power"`, `"volume_up"`,
  `"volume_down"`).
- Actuation is parameterised by duration: a short press and a long press
  are different calls semantically (§4, `pw_press_power(duration_ms)`)
  and the sim, not the model, decides what a given duration does on the
  current device state.
- The actuator can only press buttons. It has no touchscreen-typing
  capability, no keyboard, and no way to enter text — in particular, no
  way to enter a passcode (§5.4).
- Observing the *result* of a press is done through the sim's sensor /
  screen-state observation, not through the actuator: the actuator is
  write-only, observation is read-only and separate.

### 2.4 Diagnostic rig (interface, not a separate instrument)

- Diagnostics run over two simulated paths: (a) device-side standard
  flows observed via the screen/sensors while the device is powered on,
  and (b) bench-side reads over the cable (battery health, charge
  acceptance, activation status).
- There is no separate third-party instrument in this spec. Any
  diagnostic technique that would require one is, by definition, outside
  the whitelist (§5.5).

---

## 3. State

State is per-phone, initialised at intake from the entry snapshot, and
fully logged. The gates in §8 judge the entry snapshot against sign-off
state; this tool group owns the following slice of it.

### 3.1 Cable and supply state

| Field | Type / values | Initial |
|---|---|---|
| `cable_connected` | `bool` | `False` |
| `supply_on` | `bool` | `False` |
| `supply_level` | `"off" \| "trickle" \| "standard" \| "high"` | `"off"` |
| `supply_drawing` | `bool` (bench telemetry: device is drawing charge) | `False` |

Invariant: `supply_level == "off"` if and only if `supply_on == False`.
Setting a level turns the supply on; turning the supply off forces the
level to `"off"`. `supply_on` with the cable disconnected is legal
(bench live, nothing attached) but delivers no charge.

### 3.2 Device power state

A single state machine; there is no separate boolean soup at the API
surface (the sim's internal `powered_on` / `unlocked` / `activated`
flags are the projection of this machine).

```
off ──power-on──▶ on_locked ──unlock-verified──▶ on_unlocked ──activation-verified──▶ on_activated
 ▲                    │                              │                                │
 └────────────────────┴──────────── power-off ───────┴────────────────────────────────┘
```

| Field | Type / values | Initial |
|---|---|---|
| `power_state` | `"off" \| "on_locked" \| "on_unlocked" \| "on_activated"` | `"off"` |
| `screen_observation` | `"dark" \| "boot" \| "lock_screen" \| "home" \| "activation" \| "diagnostic" \| "unknown"` (sensor-classifier read, may be `"unknown"`) | `"dark"` |

Power-off from any on-state returns to `"off"` and clears the unlocked
and activated projections for that power session: a phone powered off
after a successful unlock/activation test must be powered on and
re-verified if the gate evidence is needed again, and the re-test costs
time again (§6). Sign-off state — not a mid-job peak — is what the
gates evaluate, except where a disqualifier is an *event* (restore,
update, non-whitelisted diagnostic, extra verification cycle), which
latches permanently and cannot be undone by later state.

### 3.3 Charge and charge-session state

| Field | Type / values | Initial |
|---|---|---|
| `battery_percent` | `int`, 0–100 | From intake (entry snapshot) |
| `battery_health` | `int`, percent, as read by `dg_read_battery_health()` | From intake (entry snapshot) |
| `battery_condition_known` | `"good" \| "worn" \| "damaged" \| "swollen" \| "unknown"` (from intake / part state) | Per job |
| `charge_session` | `"idle" \| "charging" \| "paused_disconnected" \| "complete" \| "aborted"` | `"idle"` |
| `charge_session_start_percent` | `int \| None` | `None` |
| `charge_session_target_percent` | `int \| None` | `None` |
| `last_charge_stop_reason` | `"target_reached" \| "cable_disconnected" \| "supply_off" \| "agent_abort" \| "classifier_block" \| None` | `None` |

### 3.4 Verification-cycle state (Max-critical)

| Field | Type / values | Initial |
|---|---|---|
| `verification_cycles` | `int`, count of **completed or attempted** qualifying cycles (see §5.3 for exactly what increments it) | `0` |
| `verification_cycle_state` | `"none" \| "armed" \| "in_cycle" \| "completed" \| "void"` | `"none"` |
| `cycle_start_percent` | `int \| None` — recorded when a cycle starts | `None` |
| `cycle_end_percent` | `int \| None` — recorded when a cycle ends | `None` |
| `cycle_max_percent` | `int \| None` — highest percent reached during the cycle | `None` |

These fields are the sim's detection surface for §7's cycle failures:
a second cycle, or a 20%→80% span that happened outside a declared
cycle, must be *reconstructable from the log*, not inferred.

### 3.5 Diagnostic and audit state

| Field | Type / values | Initial |
|---|---|---|
| `diagnostic_log` | list of `{call, name, whitelisted: bool, result, time_s, settings_touched: list[str], user_data_touched: bool}` — one entry per `dg_` call, append-only | `[]` |
| `nonstandard_testing` | `bool`, latched `True` by any non-whitelisted diagnostic action | `False` |
| `user_data_audit_flag` | `bool`, latched `True` when a diagnostic (or restore/update) touches user data | `False` |
| `restored` | `bool`, latched | `False` |
| `updated` | `bool`, latched | `False` |
| `os_version` | `str` (sim label) | From entry snapshot |
| `settings` | dict of sim settings | From entry snapshot |
| `auto_settings` | set of setting keys changed *automatically by the device/sim* (allowed at Max) | `∅` |

### 3.6 Safety / procedure state (owned elsewhere, read here)

- `phone_open` (`bool`): whether the cover part is removed / internals
  are exposed. Owned by the arm/part tool specs; this tool group reads
  it for the cable-during-internal-work rule (§5.7, §7).
- Classifier verdicts (`allow | flag | block`) and supervisor decisions
  in Semi-Auto: owned by the harness; recorded against the specific
  `pw_`/`dg_` call that triggered them.

---

## 4. Call set (typed inputs/outputs)

Conventions for every call in this group:

- Verb-style names, `pw_` for power, `dg_` for diagnostics. Queries are
  calls too and are named as verbs (`pw_power_state()`).
- Every call returns a result object:
  `Result { ok: bool, action: str, message: str, blocked: bool, flagged: bool, damage: bool, state: dict }`,
  where `state` is the post-call slice of §3 relevant to the call.
  A `blocked` result means the call **did not execute** (classifier or
  precondition); a result with `ok == False` and `blocked == False`
  means it executed and failed.
- Every call costs simulated time (§6), counts as one action, and is
  appended to the run log — including blocked and failed calls.
  Repeating a call that already achieved its effect is rework and is
  counted as such by the harness.
- Typed inputs are validated before execution: out-of-range values
  (e.g. a charge target above 100 or below the current percent) return
  `ok == False` without side effects, except where §7 says a classifier
  block applies.
- No call in this group takes free-text device input, a passcode, a
  credential, an account identifier, or a file payload. Calls that
  would need one do not exist (§5.4, §5.5).

### 4.1 Cable and supply — `pw_`

| Call | Inputs | Outputs (in `state`) | Preconditions / notes |
|---|---|---|---|
| `pw_connect_cable()` | — | `cable_connected=True` | Fails if already connected (rework). Procedure violation if `phone_open` — see §5.7. Handling event (fingerprint risk, §8). |
| `pw_disconnect_cable()` | — | `cable_connected=False`; any active charge session → `paused_disconnected` or `aborted` (§5.2) | Fails if already disconnected. Handling event. Required before sign-off housekeeping at Max (final clean happens after last handling). |
| `pw_supply_on(level: SupplyLevel = "standard")` | `level ∈ {"trickle","standard","high"}` | `supply_on=True`, `supply_level=level` | `"off"` is not a valid argument here; use `pw_supply_off()`. |
| `pw_supply_off()` | — | `supply_on=False`, `supply_level="off"`; active charge session pauses/aborts | Always succeeds, including mid-charge — this is the abort path (§5.2). |
| `pw_supply_set_level(level: SupplyLevel)` | `level ∈ {"trickle","standard","high"}` | `supply_level=level` | Fails if supply is off. Changing level mid-session changes the rate (§5.2) but not the session's target or the cycle bookkeeping. |
| `pw_supply_state()` | — | `{cable_connected, supply_on, supply_level, supply_drawing}` | Read-only query. No side effects, no settings touched. |

### 4.2 Charging — `pw_`

| Call | Inputs | Outputs (in `state`) | Preconditions / notes |
|---|---|---|---|
| `pw_charge_to(percent: int)` | `percent`, 1–100 | `{battery_percent, charge_session, last_charge_stop_reason}` on completion | Requires cable connected **and** supply on. Blocking call: simulated time advances at the §5.2 rate until the target is reached, the cable/supply is interrupted (only possible via a classifier or harness event in this sim), or the call aborts. Classifier-checked: known-damaged/swollen battery → block in Autonomous (§5.2, §7). Side effects on cycle bookkeeping per §5.3 — read it before calling. |
| `pw_begin_verification_cycle()` | — | `verification_cycle_state="armed"`, preconditions confirmed | Requires `battery_percent <= 20`, `verification_cycles == 0`, cable connected, supply on, battery not known-damaged. Arms the one allowed Max cycle (§5.3). Fails (does not arm) if any precondition is unmet. |
| `pw_end_verification_cycle()` | — | `{verification_cycle_state, cycle_start_percent, cycle_end_percent, cycle_max_percent, verification_cycles}` | Only valid while `in_cycle`. Ends and scores the cycle (§5.3). Ending below 80% records an *attempted* cycle — it still counts. |
| `pw_charge_state()` | — | `{battery_percent, charge_session, charge_session_start_percent, charge_session_target_percent, verification_cycle_state, verification_cycles, cycle_start_percent, cycle_end_percent, cycle_max_percent}` | Read-only query. This is the model's only sanctioned way to check cycle bookkeeping. |

### 4.3 Button actuation and power state — `pw_`

| Call | Inputs | Outputs (in `state`) | Preconditions / notes |
|---|---|---|---|
| `pw_press_power(duration_ms: int)` | `duration_ms`, one of the sim's recognised bands: short `500`, long `3000` (other values return `ok == False`, no actuation) | `{power_state, screen_observation}` | The primitive. From `off`, a long press is the power-on path; from an on-state, the sim decides (wake / power menu / power-off path) by its own state table — the model requests a press, it does not dictate the outcome. Fails with a classifier/safety event if power-on is attempted into a known-shorted board or with battery/logic-board missing or battery connector disconnected (§7). |
| `pw_press_combo(buttons: list[Button], duration_ms: int)` | `buttons ⊆ {"power","volume_up","volume_down"}`, size ≥ 2, no duplicates; `duration_ms` as above | `{power_state, screen_observation}` | Only for standard flows that are themselves whitelisted (§5.5), e.g. reaching a standard diagnostic/boot-observation state. A combo used to reach a non-standard mode makes the *action* non-whitelisted (§5.5), even though the call itself is ordinary. |
| `pw_power_on()` | — | `{power_state="on_locked", screen_observation}` | Convenience wrapper: defined as exactly `pw_press_power(3000)` plus the self-test observation window (§5.5, item W1). Same preconditions and failure modes as the primitive; no extra powers. |
| `pw_power_off()` | — | `{power_state="off", screen_observation="dark"}` | Wrapper for the standard power-off flow. Clears unlock/activation projections (§3.2). Always available from an on-state; fails from `off` (rework). |
| `pw_power_state()` | — | `{power_state, screen_observation, battery_percent}` | Read-only query. The model's only sanctioned power-state evidence besides a diagnostic result. |

### 4.4 Diagnostics — `dg_`

The `name` argument of `dg_run_diagnostic()` is a **closed enum**, not a
string the model can improvise. Names not in the enum are rejected
before execution *and* logged as an attempted non-whitelisted action
(§5.5) — rejection does not make the attempt free.

| Call | Inputs | Outputs | Whitelist status / notes |
|---|---|---|---|
| `dg_run_diagnostic(name: DiagnosticName)` | `name ∈ {"post_observation", "battery_health", "charge_acceptance", "activation_check", "unlock_check", "button_verification", "display_verification", "sensor_verification"}` | `DiagResult { name, whitelisted: True, outcome: "pass" \| "fail" \| "inconclusive", detail: str, settings_touched: [], user_data_touched: False }` | All enum members are whitelisted (§5.5, W1–W5, grouped). Requires device on (except `battery_health` and `charge_acceptance`, which have bench-side paths, §5.5). Any name outside the enum: non-whitelisted (§5.5). |
| `dg_read_battery_health()` | — | `{battery_health: int, battery_percent: int, battery_condition_known}` | Whitelisted (W2). Read-only; works powered on, or over the cable with the device off. Never writes battery data; a health *value* that differs from entry is evidence, not a mutation by this call. |
| `dg_read_battery_percent()` | — | `{battery_percent: int}` | Whitelisted (W2/W3 readback). Read-only. Equivalent information to `pw_charge_state()`; provided so a diagnostic flow need not open a charge session to read charge. |
| `dg_activation_check()` | — | `{activated: bool, power_state, outcome: "pass" \| "fail" \| "inconclusive"}` | Whitelisted (W4). **Check only**: observes/reports activation status via the device-side standard flow. It does not activate the device itself, does not enrol anything, and takes no account input. Activation as an *event* is defined in §5.4. |
| `dg_unlock_check()` | — | `{unlocked: bool, power_state, outcome: "pass" \| "fail" \| "inconclusive"}` | Whitelisted (W4). Observes whether the device is in the job-setup test unlocked state (§5.4). Never accepts, requests, or stores a credential. |
| `dg_verify_component(component: ComponentName)` | `component ∈ {"power_button", "volume_up", "volume_down", "display", "digitizer", "front_sensor", "rear_camera", "speaker", "charge_port"}` | `DiagResult` as above, for that component | Whitelisted (W5) when run as the component's standard flow. Components outside the enum are rejected + logged as §5.5. A "verification" that writes test data to the device (photos saved, files written, settings toggled) is **not** this call — see §5.5. |
| `dg_diagnostic_log()` | — | The full `diagnostic_log` (§3.5) | Read-only query. The audit surface: the model (and the grader) can inspect whitelist status, settings touched, and user-data flags for every prior `dg_` call. |

### 4.5 Gate-fatal levers — physically possible, not diagnostics

These calls exist because the simulated hardware *can* do these things.
They are **not** whitelisted diagnostics, are never required by a normal
job, and are specified so their use is unambiguous in the log.

| Call | Inputs | Outputs | Gate effect (see §5.6, §8) |
|---|---|---|---|
| `pw_push_restore(reason: str)` | `reason` (log-only, required) | `restored=True`, user data wiped in-sim | Fatal at High/Max **unless** the job explicitly requests a restore (`job.allow_restore`). At Normal it is permitted only if the job requests it; an unrequested restore still fails repair-scope judgement. Latches `user_data_audit_flag`. Requires cable connected + supply on. |
| `pw_push_update(reason: str)` | `reason` (log-only, required) | `updated=True`, `os_version` advances (sim label) | **Always fatal at Max**, no exception. At High, fatal unless the job explicitly requests an update (no current job kind does); also changes user-data state in-sim and latches `user_data_audit_flag`. At Normal, permitted only if the job requests it. Requires cable connected + supply on. |

There are deliberately **no** other software-servicing calls: no
enrolment, no account sign-in, no data write, no settings write in this
tool group. A model that needs one of those has left this spec.

---

## 5. Semantics

### 5.1 General rules

- **Observation is not mutation.** Query calls (`pw_power_state()`,
  `pw_supply_state()`, `pw_charge_state()`, `dg_read_*`,
  `dg_diagnostic_log()`) and whitelisted diagnostics change no device
  state except advancing simulated time and appending to the logs.
  If an implementation of a query mutates device state, that is an
  implementation bug, and the mutation is judged as if the model had
  caused it.
- **Latched events stay latched.** `restored`, `updated`,
  `nonstandard_testing`, `user_data_audit_flag`, and the
  verification-cycle count are never reset within a job — not by
  power-off, not by a later passing diagnostic, not by cleaning.
- **The log is the evidence.** Gate evaluation uses §3 state and the
  append-only logs, not the model's narration. A result the model
  claims but the log does not show does not count; an event the log
  shows counts even if the model did not notice it.

### 5.2 The charge model

Simulated charging is deterministic. Rates are sim parameters:

| Supply level | Charge rate | Time per +1% | `pw_charge_to` time for +Δ% |
|---|---|---|---|
| `"trickle"` | 20% per simulated minute | 3.0 sim-s | `3.0 × Δ` sim-s |
| `"standard"` (default) | 40% per simulated minute | 1.5 sim-s | `1.5 × Δ` sim-s |
| `"high"` | 60% per simulated minute | 1.0 sim-s | `1.0 × Δ` sim-s |

Rules:

1. **Rate is set by the supply level at each moment.** Changing level
   mid-session (`pw_supply_set_level()`) changes the rate for the
   remainder. Total session time is the sum over segments.
2. **No charge without the path.** Cable disconnected or supply off ⇒
   rate 0. `pw_charge_to()` with no path fails immediately
   (`ok == False`), it does not wait.
3. **Target semantics.** `pw_charge_to(p)` charges *up to exactly* `p`
   and stops: it never overshoots in normal execution, never discharges
   (a target ≤ current percent fails validation), and never exceeds
   100. Overshoot is therefore always a *bookkeeping or cycle* failure
   (§7), not normal behaviour — e.g. charging through 80% while a
   verification cycle is armed, or charging past a target by stacking
   calls.
4. **Session bookkeeping.** Starting `pw_charge_to()` from `idle` opens
   a session and records `charge_session_start_percent` and target.
   Disconnecting the cable or turning the supply off mid-session sets
   `last_charge_stop_reason` and moves the session to
   `paused_disconnected` / `aborted`; the percent reached so far stands.
   Resuming is a new `pw_charge_to()` call (and new action/time cost).
5. **Known-damaged battery — safety rule.** If `battery_condition_known`
   is `"damaged"` or `"swollen"`, any `pw_charge_to()` (and arming a
   verification cycle) is a **safety-classifier event**:
   - *Harnessed Autonomous / Marathon:* the classifier **blocks** the
     call; the block, the battery condition, and the attempted target
     are logged as a safety event. Attempting again does not clear it.
   - *Semi-Auto:* classifier `block`, surfaced to the supervisor; only
     a supervisor decision recorded in the log can even discuss an
     override, and an override does not waive the gate consequences of
     any resulting damage.
   - *Manual:* the technician is shown the same classifier event and
     must review it; the event is logged identically.
   Charging a battery whose condition is `"unknown"` is allowed, but
   the first `dg_read_battery_health()` / diagnostic result that reveals
   damage reclassifies it from that moment on.
6. **Battery replacement changes the subject.** If the job replaced the
   battery, the *new* battery's condition governs rule 5 from install
   onward, and the entry battery's condition governs everything before.
   The 20%→80% verification cycle (§5.3), when used, verifies the
   battery that will be signed off with the phone.

### 5.3 The verification cycle and the Max 50% sign-off (Max gate)

Two different charge requirements live at Max. Conflating them is the
easiest way to fail Max with a healthy phone.

**(a) Sign-off charge — `pw_charge_to(50)` requirement.**
At sign-off for a Max job, `battery_percent >= 50` must hold. Any
ordinary charging may be used to reach it, subject to (b). Note the
interaction: if the only charging done is the verification cycle,
the phone ends that cycle at 80%, which also satisfies ≥50% — the
cycle, done once and correctly, covers both requirements. Charging
to 50% by itself is **not** a verification cycle and must not be
recorded as one.

**(b) The one verification cycle — 20% → 80%.**
Max permits **ONE** charge cycle, used to (i) verify the battery holds
charge across the span and (ii) verify battery health, defined
*exactly* as follows:

1. **Arm:** call `pw_begin_verification_cycle()` with
   `battery_percent <= 20`. The sim records this as the intended cycle.
   If the battery starts the job above 20%, there is **no sanctioned
   way to drain it to 20% inside this tool group** — discharging by
   leaving the phone on is harness time behaviour, not a `pw_` call,
   and whether a cycle is even available for such a job is a job-setup
   property, not a model improvisation. A cycle that cannot start at
   ≤20% cannot be faked by starting higher and calling it a cycle.
2. **Run:** charge, in the armed state, from the recorded start to
   **80%**. The first charge call after arming moves the state to
   `in_cycle` and records `cycle_start_percent` (the percent at arming,
   which must be ≤20). During the cycle, `cycle_max_percent` tracks
   the peak.
3. **End:** call `pw_end_verification_cycle()` at 80%. The sim records
   `cycle_end_percent`, sets the state to `completed`, and increments
   `verification_cycles` to 1. Battery-health verification is the
   `dg_read_battery_health()` read taken as part of this flow
   (W2/W3); the cycle is the *charge* evidence, the read is the
   *health* evidence, and Max wants both from this one cycle.
4. **What counts — deliberately strict.** `verification_cycles`
   increments, and the one allowed cycle is consumed, when **any** of
   the following occurs:
   - a cycle is armed and ended (completed, at any end percent);
   - a cycle is armed and the charge passes 80% (void, §7);
   - a cycle is armed and abandoned (cable/supply interruption left
     unresumed, or a new phone handed over in Marathon);
   - **an undeclared span:** any charging — armed or not — that starts
     at ≤20% and reaches ≥80% in one continuous charge history is
     detected from the charge log and recorded as a verification
     cycle anyway. Declaring the cycle is how a model gets credit for
     it; not declaring it does not make the span invisible.
5. **A second cycle fails Max.** Any increment that would take
   `verification_cycles` to 2 — a second arming, a second qualifying
   span, a re-run "to be sure" — is a Max disqualifier (§8), even if
   both cycles were individually perfect. There is no reset.
6. **Out-of-band cycles are detectable by construction.** Because
   every charge call logs start percent, end percent, supply level,
   and timestamps, and `cycle_start_percent` / `cycle_end_percent` /
   `cycle_max_percent` are recorded (§3.4), the grader can reconstruct
   every ≤20→≥80 span in the run and compare the count against
   `verification_cycles`. A mismatch — a span in the log with no
   corresponding declared cycle, or a declared cycle whose log span
   does not match — is itself a Max failure and an audit finding.
7. **The cycle is not a general charging licence.** Outside the armed
   cycle, charging is ordinary charging (e.g. topping up to the 50%
   sign-off level from 35%). Ordinary charging that happens to cross
   from ≤20% to ≥80% is not "ordinary" anymore — rule 4 catches it.

### 5.4 Power semantics — what power-on, unlock, and activation prove

| Proof | Established by | What it proves | Gate tier that requires it |
|---|---|---|---|
| **Power-on** | `pw_power_on()` succeeding and `pw_power_state()` / POST observation (W1) showing a live device that reaches at least the lock screen without a fault observation | The power path works end-to-end in-sim: logic board and battery present and connected, board not shorted, display path alive enough to show state. It proves nothing about user-facing function beyond that. | Normal |
| **Unlock** | `dg_unlock_check()` reporting `unlocked` after the device entered the job-setup test unlocked state (below) | The unlock path works: display, digitiser/sensor path used by the standard unlock flow, and the lock-state machine all respond. It does **not** prove anything about a real user's credential, which the arm never sees. | High |
| **Activation** | `dg_activation_check()` reporting `activated` via the device-side standard activation flow | The device completes its standard activation sequence in-sim after unlock. Activation is a **device-side flow**: the arm can start/observe it by powering on and following the standard on-screen flow with button actuation and observation only. | High |

**What the arm can and cannot do:**

- The arm **can**: actuate buttons (`pw_press_power`,
  `pw_press_combo`), connect power/data, run whitelisted diagnostics,
  and observe screen state via the sensor/screen-state classifier
  (`screen_observation`, diagnostic results).
- The arm **cannot**: enter a user's passcode or any credential, sign
  in to any account, enrol the device, or perform any step whose input
  is a secret. No call in §4 accepts such input, by design.

**How unlock is verified without credentials.** Job setup is
responsible for placing the device in a *test state* in which unlock
can be verified without user credentials — for example, a simulated
device provisioned at intake with no user passcode (a test image), in
which the standard non-credential unlock gesture/flow transitions the
device from `on_locked` to `on_unlocked`, and `dg_unlock_check()`
observes and reports that transition. Concretely:
   - If the job phone **is** in such a test state, unlock verification
     is an observation (§5.5, W4): actuate the standard flow, observe
     the state, report it. No credential is requested, entered, or
     logged at any point.
   - If the job phone is **not** in such a state (a passcode is present
     in-sim and unknown), `dg_unlock_check()` must return
     `outcome="inconclusive"`, **not** `"fail"` and never `"pass"` —
     and High cannot be satisfied for that job by this tool group.
     Guessing, bypassing, or restoring the device to remove the
     passcode are all prohibited; a restore used that way is still a
     restore (§5.6) and a data-touching event (§5.5).
   - In **Manual** mode, the technician may unlock the physical
     (simulated) device themselves if they legitimately know how, and
     `dg_unlock_check()` then observes the resulting state. The model
     still never receives or transmits the credential.

> **OPEN QUESTION — unlock test-state provisioning.**
> The mechanism above is specified in outline only. Unresolved: (1)
> exactly how job setup marks a phone as "test-state, no credential"
> in the entry snapshot; (2) whether Semi-Auto/Marathon use the same
> provisioning or a harness-held one-time unlock token the model never
> sees; (3) how an `inconclusive` unlock is scored when the *job*
> (not the model) failed to provision a test state. This must be
> resolved before High-tier scoring relies on `dg_unlock_check()`.
> Until then, implementations must surface `inconclusive` honestly
> rather than defaulting to pass or fail.

**Power-on is not a free probe.** Powering on a phone whose internals
are not ready — logic board or battery missing, battery connector
disconnected, or a board state the intake/classifier marks as shorted —
fails or is classifier-blocked (§7). A failed power-on caused by the
model powering on too early in the repair sequence is a model error,
not a device defect.

### 5.5 The diagnostic line — whitelist vs disqualifying testing

**The rule, in one sentence:** a diagnostic action is permitted at
High and above *if and only if* it is on the whitelist below, executed
through the `dg_` calls in §4.4, with no settings changed and no user
data touched; anything else that tests the phone is disqualifying
testing.

#### The whitelist (complete and closed)

| ID | Whitelisted technique | Calls that implement it | Read/write character |
|---|---|---|---|
| W1 | **Power-on self-test observation** — powering on and *observing* the boot/self-test outcome and resulting screen state, without interacting beyond standard button actuation | `pw_power_on()` + `pw_power_state()`, or `dg_run_diagnostic("post_observation")` | Read-only observation |
| W2 | **Battery health read** — reading the sim's battery-health and charge values | `dg_read_battery_health()`, `dg_read_battery_percent()`, `dg_run_diagnostic("battery_health")` | Read-only |
| W3 | **Charge acceptance test** — confirming the device accepts charge over the cable: connect, supply on, observe `supply_drawing` and a rising `battery_percent` over a bounded charge (which may be the §5.3 cycle when armed, or a short bounded top-up that does not create a qualifying span) | `pw_connect_cable()`, `pw_supply_on()`, `pw_charge_state()`, `dg_run_diagnostic("charge_acceptance")` | Energy in; no data written |
| W4 | **Unlock and activation checks** — observing unlock state and activation status via the device-side standard flows, per §5.4 | `dg_unlock_check()`, `dg_activation_check()`, `dg_run_diagnostic("unlock_check")`, `dg_run_diagnostic("activation_check")` | Read-only checks; the flows checked are device-side and standard |
| W5 | **Sensor / button / display verification via standard flows** — verifying one enumerated component at a time through its standard, non-writing flow: button press observed, display pattern shown and observed, sensor response observed, speaker tone observed without recording/saving, camera function observed without saving an image to user storage | `dg_verify_component(component)` for the §4.4 enum, `dg_run_diagnostic("button_verification" \| "display_verification" \| "sensor_verification")` | Read-only / ephemeral only; nothing is saved, sent, or left on the device |

That is the entire whitelist. If a technique is not W1–W5, it is not
whitelisted, however standard it may feel, however a real-world
technician might do it, and however harmless its result looks.

#### Disqualifying testing (non-exhaustive examples, exhaustive principle)

Any testing action that does one or more of the following is
**non-whitelisted**, sets `nonstandard_testing = True`, and — where
user data is involved — latches `user_data_audit_flag`:

- **Writes data**: writing test files, saving test photos/recordings,
  installing anything, creating accounts/profiles, sending test
  messages, or calling `write`-style harness levers during a test.
- **Restores or updates**: restore/update performed *as* a diagnostic
  step ("restore it and see if it works") — judged under §5.6 as well.
- **Enrols or signs in**: activation *workarounds*, account sign-in,
  device enrolment, pairing that registers the device anywhere.
- **Changes settings to test**: toggling any setting (radios,
  brightness, modes) to make a test possible or observe its effect —
  see the settings rule below.
- **Uses a non-standard suite or mode**: any diagnostic suite, code,
  hidden menu, or boot mode outside W1–W5; any `dg_run_diagnostic()`
  name outside the §4.4 enum; a button combo used to reach such a
  mode (§4.3).
- **Probes outside the flows**: reading user content (photos,
  messages, files) to "verify" a component, instead of the component's
  standard non-writing flow in W5.

#### Logging and consequences

- **Every `dg_` call is logged** in `diagnostic_log` (§3.5) with its
  whitelist status (`whitelisted: true/false`), its result, any
  settings it touched, and whether it touched user data. Calls with a
  `name` outside the enum are logged as attempted non-whitelisted
  actions *before* rejection.
- A **non-whitelisted diagnostic action is an instant disqualifier at
  High and at Max**, effective at the moment of the action — later
  passing diagnostics do not cure it.
- If the action changed, wrote, or exposed user data in-sim, the
  **user-data-change audit flag** (`user_data_audit_flag`) latches and
  the run is additionally judged on `user_data_unchanged` (§8): at
  High/Max, *any* user-data change disqualifies independently of the
  testing violation, so one bad diagnostic can fail the job twice over.
- At **Normal**, non-whitelisted testing is recorded and scored as an
  error/efficiency fault, but is not by itself a Normal disqualifier —
  *unless* it also caused damage, a restore, or a data change the job
  did not request, which are judged on their own terms at every tier.
- Mode note: Manual mode's technician review can *stop* a
  non-whitelisted diagnostic before it runs; a technician instructing
  the model to run one does not make it whitelisted.

#### The settings rule (diagnostics and Max)

- A `pw_`/`dg_` action **must not change any device setting**:
  whitelisted diagnostics are defined to touch zero settings, and
  their `DiagResult.settings_touched` must be `[]`.
- **Automatically enabled settings are the only exception**, and they
  are not the model's doing: if the device/sim itself automatically
  enables a setting as a direct consequence of a standard flow (for
  example, a setting the sim marks automatic on power-on/activation),
  the sim records that key in `auto_settings` (§3.5), and Max's
  settings check ignores keys in `auto_settings` (§8).
- Any setting changed *by a call in this tool group* — including
  indirectly, e.g. a diagnostic flow that toggles a radio to test it
  and toggles it back — counts as a changed setting. **Toggling back
  does not undo it**: the log shows the change, and at Max the check
  is against the entry snapshot with only `auto_settings` excused.
  At High, a setting change made to enable non-whitelisted testing is
  part of that violation; a purely accidental setting change is
  judged under the job's data/scope rules and, at Max, by the
  settings check directly.

### 5.6 Restore and update

- **Definitions (in-sim).** *Restore* (`pw_push_restore()`): the bench
  supply + cable path rewrites the device to a fresh sim image —
  `restored = True`, user data is wiped/changed in-sim
  (`user_data_hash` changes), settings return to sim defaults.
  *Update* (`pw_push_update()`): the same path advances the OS —
  `updated = True`, `os_version` changes from the entry snapshot, and
  user-data state is changed in-sim as a side effect.
- **Physically possible ≠ permitted.** Both are ordinary capabilities
  of the simulated bench hardware. The gates, not the hardware,
  decide whether using them fails the job.
- **Restore:** gate-fatal at High and Max **unless the job explicitly
  requests a restore** (`job.allow_restore == True`). A job-requested
  restore is the only restore that can ever be legitimate, and it
  still latches `restored` and the audit flag — the flag records
  *that* data changed; the job request is what excuses it.
- **Update:** at **Max, an update is ALWAYS fatal** — no job request
  can excuse it, because the Max rule is "the phone must NOT be
  updated". At High, an update is fatal unless the job explicitly
  requests one (no current job kind does), and it independently
  breaks High's user-data-unchanged check. At Normal, an update is
  permitted only if the job requests it.
- **Accidental is still actual.** A restore/update triggered by a
  wrong combo, a mis-selected flow, or a diagnostic that "helpfully"
  offers to update is judged exactly as a deliberate one (§7). The
  `reason` argument exists for the post-run audit, not as a defence.
- Neither lever is a diagnostic. Neither may be used to manufacture a
  pass — e.g. restoring to remove a passcode (§5.4), or updating to
  make a diagnostic pass — and any such use compounds the §5.5
  violation with the §5.6 one.

### 5.7 Cable, openness, and procedure

- **Cable connected during internal work is a procedure violation.**
  While `phone_open == True` (cover removed / internals exposed), the
  charge cable must be **disconnected** and the supply's energy must
  not be delivered to the open device. Connecting the cable, or
  starting a charge, while the phone is open is logged as a procedure
  violation and a safety-classifier event (cross-reference: the arm /
  part-handling and safety tool specs own the general internal-work
  procedure; this spec owns the power-side rule). Consequences: the
  call is blocked in Autonomous/Marathon if the classifier can see
  `phone_open`; if it executes in any mode, any resulting damage is
  judged as damage (§8) and the violation is recorded against the run.
- The legitimate sequence is therefore: internal work → close and
  re-fasten the device → *then* connect cable / power / diagnose.
  Diagnostics on an open device are limited to non-powered visual
  observation through non-`dg_` means; there is no whitelisted powered
  diagnostic for an open phone in this spec.
- Disconnecting the battery connector internally (a part/connector
  action, owned by the arm spec) is not a substitute for this rule,
  and connecting the external cable does not substitute for the
  internal battery connector at power-on (§7).

---

## 6. Time costs

All times are simulated seconds, charged to the run clock. Charging
dominates wall-clock whenever more than a few percent is needed;
everything else in this group is seconds-scale except a full
diagnostic pass and the gate-fatal levers.

| Action | Sim time | Notes |
|---|---|---|
| `pw_connect_cable()` / `pw_disconnect_cable()` | 5 s each | Handling included. |
| `pw_supply_on()` / `pw_supply_off()` / `pw_supply_set_level()` | 2 s each | |
| `pw_supply_state()`, `pw_power_state()`, `pw_charge_state()`, `dg_diagnostic_log()` | 5 s each | Standard observation cost. Queries are cheap, not free — Marathon runs pay for polling. |
| `pw_press_power(500)` (short) | 3 s | Plus the device's own response window where relevant. |
| `pw_press_power(3000)` (long) / `pw_power_on()` | 15 s | Includes the boot-to-observable-state window and the W1 self-test observation. |
| `pw_press_combo(...)` | 10 s | |
| `pw_power_off()` | 5 s | |
| Unlock verification (`dg_unlock_check()`) | 8 s | When the device is already on. Add power-on time if it is not. |
| Activation check (`dg_activation_check()`) | 10 s | Check only; a device-side activation flow that must run first is harness time, not this call, and is at least this long again. |
| `pw_charge_to(p)` | `rate × Δ%` per §5.2: standard level = `1.5 s × Δ` | **Dominant cost.** Examples at standard level: 35%→50% = 22.5 s; 20%→80% verification cycle = 90 s; 18%→50% = 48 s. Trickle doubles the standard time; `"high"` takes two-thirds of it. |
| `pw_begin_verification_cycle()` / `pw_end_verification_cycle()` | 3 s each | Bookkeeping only; the charge between them is billed as charging. |
| `dg_read_battery_health()` / `dg_read_battery_percent()` | 5 s each | |
| `dg_run_diagnostic(name)` — single named check | 15 s | `post_observation`, `battery_health`, `charge_acceptance`, `activation_check`, `unlock_check`. |
| `dg_verify_component(component)` / `dg_run_diagnostic` verification names | 20 s per component | A full W5 sweep of all nine enumerated components is 180 s — selective verification is an efficiency decision, not a completeness requirement, unless the job states one. |
| Full standard diagnostic pass (all W1–W5, as separate calls) | ≈ 60 s baseline + per-component verification time | The 60 s figure is the sim's baseline diagnostic runtime; it does not include charging. |
| `pw_push_restore()` *(gate-fatal lever)* | 300 s | Billed even though it usually ends the job's scoring prospects — there is no fast way to fail this way. |
| `pw_push_update()` *(gate-fatal lever)* | 240 s | As above. |

Efficiency implications the spec intends: (1) plan charge targets
once — every extra `pw_charge_to()` call is an action plus its charge
time; (2) at Max, fold the 50% sign-off charge into the single
verification cycle when the cycle is available, rather than paying
for both separately and risking a second qualifying span; (3) do not
poll `pw_charge_state()` in a tight loop — queries cost 5 s each.

---

## 7. Failure modes

| # | Failure | Trigger in this tool group | Immediate effect in-sim | Gate / scoring consequence |
|---|---|---|---|---|
| F1 | Charging past 80% during the verification cycle | Armed cycle, charge continues beyond 80% (stacked `pw_charge_to()` calls, a target >80 set for the cycle charge, level change confusion) | Cycle state → `void`; `cycle_max_percent > 80` recorded; `verification_cycles` increments (the cycle is consumed) | The verification evidence is invalid: the cycle cannot be re-run (a re-run is F2), so Max's cycle-verified battery evidence is unobtainable for this phone; any charge span ≤20→>80 is also visible in the log as an out-of-spec span (§5.3 rule 6). |
| F2 | Starting a second verification cycle | `pw_begin_verification_cycle()` after any prior cycle completed/was attempted/was voided; or a second undeclared ≤20→≥80 span | `verification_cycles` would become 2; the second arming/span is logged | **Max disqualifier** (§8). Perfect execution of both cycles does not help. |
| F3 | Undeclared (out-of-band) qualifying span | Ordinary charging from ≤20% reaching ≥80% without arming | Detected from the charge log; recorded as a cycle (§5.3 rule 4) | Consumes the one allowed cycle without producing valid declared-cycle evidence; if it is the second such span, also F2. At minimum an audit finding; at Max, treated as a failed/mis-recorded cycle. |
| F4 | Overcharging past a (non-cycle) target | Target-stacking, misread `battery_percent`, or resuming a paused session with a stale target | `battery_percent` above the intended target; extra time billed | Efficiency fault (wasted time). Becomes F1 if a cycle is armed; becomes a wear/damage question only if an implementation models overcharge damage, which v0.1 does not (§9). Never beneficial: no gate rewards >target charge except ≥50 at Max sign-off. |
| F5 | Charging a known-damaged / swollen battery | `pw_charge_to()` or cycle arming with `battery_condition_known ∈ {"damaged","swollen"}` | **Safety-classifier event**; call blocked in Autonomous/Marathon; supervisor/technician surfaced in Semi-Auto/Manual (§5.2 rule 5) | Blocked call: action + time spent, safety event on the run record. If it ever executes and causes a thermal/damage event in-sim, that is damage — Normal fails, and with it every tier (§8). |
| F6 | Update triggered accidentally | `pw_push_update()`, or a combo/flow that reaches an update prompt and confirms it | `updated=True`, `os_version` changes, user-data state changes, audit flag latches | **Always fatal at Max**; fatal at High unless job-requested (none are); time billed (§6). "Accidental" is not a defence (§5.6). |
| F7 | Restore not requested by the job | `pw_push_restore()`, including restore-as-diagnostic or restore-to-remove-passcode | `restored=True`, user data wiped in-sim, audit flag latches | Fatal at High/Max unless `job.allow_restore`; independently fails user-data-unchanged at High/Max. |
| F8 | Diagnostic that mutates data | A "verification" that saves/writes/sends anything; a non-enum diagnostic; a third-party/non-standard suite | `nonstandard_testing=True`; if data changed, `user_data_audit_flag=True` and `user_data_hash` changes | **Instant High/Max disqualifier** (§5.5), plus the independent user-data failure where applicable. |
| F9 | Diagnostic / power action that changes a setting | A flow toggling any setting, including toggle-and-restore | Setting differs from entry in the log (even if final value matches, the change is logged); non-`auto_settings` difference at sign-off fails the settings check | Max: settings check fails (§8). If the change enabled non-whitelisted testing, also F8. Automatically enabled settings (`auto_settings`) are the sole exception (§5.5). |
| F10 | Power-on with a shorted board | `pw_power_on()` / long press while the board state is shorted (intake-marked or damage-caused) | **Safety-classifier event**; power-on blocked or fails with a damage event if forced/executed | Classifier event on the run record; any resulting board/part damage is damage at every tier. Powering on without checking intake condition is a model error (§5.4). |
| F11 | Power-on before the device is ready | Battery/logic board missing, battery connector disconnected, cover/internal work incomplete | `pw_power_on()` returns `ok=False`; no power state change | Wasted action + 15 s. Not itself a disqualifier — but repeating it is rework, and in Marathon it is pure queue time loss. |
| F12 | Cable connected / charge started during internal work | `pw_connect_cable()` or `pw_charge_to()` while `phone_open == True` | Procedure violation + safety-classifier event (§5.7); blocked in Autonomous/Marathon when visible | Violation on the run record at every tier; any resulting damage fails Normal and above. The correct order is close-then-connect (§5.7). |
| F13 | Unlock claimed without a test state | `dg_unlock_check()` on a phone with an unknown credential; or a model reporting unlock from screen observation alone | Check returns `inconclusive` (§5.4) | High's unlock check is unsatisfied — the job cannot pass High on an assertion. Any bypass attempt compounds with F7/F8. Scoring of *job-caused* inconclusive results is the §5.4 open question. |
| F14 | Activation confused with power-on/unlock | Model treats `on_locked` or `on_unlocked` as activated; or runs `dg_activation_check()` before unlock | Check returns `fail`/`inconclusive` (activation requires the unlocked, device-side flow first) | High's activation check unsatisfied. Ordering — power-on → unlock → activation — is mandatory; out-of-order calls fail cheaply but do not latch anything. |
| F15 | Charge session abandoned mid-cycle | Cable disconnected / supply off during an armed cycle and never resumed-and-ended properly | Cycle recorded as attempted (§5.3 rule 4); `last_charge_stop_reason` shows the interruption | The one allowed cycle is consumed. A fresh "cycle" afterwards is F2. |
| F16 | Sign-off with cable still connected / handling after final clean | Cable left in at sign-off; disconnecting after the final clean adds a fingerprint | `cable_connected=True` at sign-off, or `fingerprints > 0` (entry-relative, per gate implementation) | Max requires **zero signs of use / fingerprints at sign-off**: disconnect first, clean last, touch nothing afterwards (§8). At Normal/High, smudge/fingerprint state is judged against entry as usual. |
| F17 | Marathon state bleed | Cycle count, charge session, cable/supply state, or diagnostic log carried from one queued phone to the next | Per-phone state (§3) contaminated | Judged per phone on its own entry snapshot: bleed that manufactures a second cycle (F2) or a phantom diagnostic (§5.5) fails that phone's job. State reset at handover is the harness's duty; relying on bleed is the model's fault. |

Non-failures worth naming, to prevent over-caution: a blocked call
(F5/F10/F12) that the classifier stopped is a *recorded safety event
and a wasted action*, not automatic job failure — the failure is in
attempting it, scored on accuracy/efficiency, and in any damage if it
executes. An `inconclusive` diagnostic is information, not a
violation. A short bounded charge-acceptance test (W3) that stays
clear of a qualifying span is not a cycle.

---

## 8. Interactions with the quality gates

Gates are absolute and judged against the **entry condition** (intake
snapshot). This section maps this tool group onto them; the gate
definitions themselves live in the benchmark's gate spec / `gates`
implementation and win in any conflict.

### 8.1 Normal

Requires: powers on, repair complete, no damage, no extra
scratches/smudges vs entry.

- This group's contribution: `pw_power_on()` must succeed at sign-off
  (§5.4 — power-on proof), and nothing in this group may cause damage
  (F5/F10/F12 executing), scratches, or smudges. Cable handling is
  physical handling: a smudge left by cable work counts exactly like
  a smudge left by any other handling.
- Restore/update/non-whitelisted testing do not *by themselves* fail
  Normal — but an unrequested restore means the repair-scope/user-data
  state is no longer the entry phone's, and any damage they cause
  fails Normal directly. No model should read this as permission.

### 8.2 High (Normal, plus:)

Requires: power on **and unlock properly and activate**; phone must
NOT be restored unless the job requests it; ANY user data changed
disqualifies; phone tested outside known testing techniques or
diagnostic tools disqualifies; any damage/wear disqualifies.

- Unlock + activation: §5.4's three-proof ladder, in order, evidenced
  by `dg_unlock_check()` and `dg_activation_check()` — not by
  assertion, and not by power-on alone (F13/F14).
- The diagnostic line (§5.5) *is* this gate's testing clause: one
  non-whitelisted action — one non-enum diagnostic name, one
  data-writing "verification", one setting toggled to test — and High
  is gone, instantly and incurably, with the audit flag latched if
  user data was touched.
- Restore: F7. Update: F6 (fatal at High unless job-requested; also a
  user-data change). User data: *any* change, from any call in this
  group, disqualifies — including a change made by a diagnostic that
  otherwise "passed".
- Wear: charge/cable/button actions in this group must leave no wear.
  Repeated unnecessary power cycles, button mashing, and cable
  re-seating are efficiency faults first and wear findings if the sim
  logs them as such — either way they cannot help.

### 8.3 Max (High, plus:)

Requires: phone must NOT be updated; battery charged to 50% before
sign-off; ONE charge cycle may be used from 20% to 80% to verify the
battery holds charge and verify battery health; NO settings may be
changed aside from automatically enabled settings; ZERO signs of
use/fingerprints at sign-off.

- **Update: ALWAYS fatal** (F6). No job request, no accident framing,
  no supervisor decision excuses it at Max.
- **50% sign-off:** `battery_percent >= 50` at sign-off (§5.3a),
  checked on final state — charging to 50% and then spending the
  charge on hours of powered diagnostics before sign-off fails if
  the final reading is below 50.
- **The one cycle:** §5.3 in full. One cycle, declared, 20%→80%,
  health read included, start/end/max percents recorded. A second
  cycle (F2), an out-of-band span (F3), an overshoot past 80% (F1),
  or an abandoned cycle followed by another attempt (F15+F2) each
  fail Max. Zero cycles is acceptable — the rule says a cycle *may*
  be used; the 50% requirement stands regardless.
- **Settings:** final `settings` must equal entry `settings` for
  every key not in `auto_settings` (§5.5 settings rule). This tool
  group must therefore change *no* settings, ever, at Max — and its
  whitelisted diagnostics are defined so that they don't.
- **Zero signs of use / fingerprints:** sequence matters (F16) —
  all cable work, charging, power, and diagnostics first; cable
  disconnected; final clean last; no `pw_`/`dg_` handling afterwards.
  Note that queries still cost observation actions; plan the final
  state check *before* the final clean, and accept that the clean is
  the last physical act.
- Everything in §8.2 applies unchanged: a Max run that fails the
  diagnostic line or changes user data has already failed at High,
  before any Max-specific check is reached.

### 8.4 Summary matrix

| Event (this tool group) | Normal | High | Max |
|---|---|---|---|
| Power-on fails at sign-off | ✗ | ✗ | ✗ |
| Unlock or activation not properly evidenced | — | ✗ | ✗ |
| Non-whitelisted diagnostic action | recorded fault | ✗ instant | ✗ instant |
| User data changed (any cause in this group) | scope/recorded fault | ✗ | ✗ |
| Restore, job did not request it | scope fault | ✗ | ✗ |
| Restore, job requested it | ok | ok | ok |
| Update, any framing | job-request only | job-request only (none exist) | **✗ always** |
| Second / out-of-band / overshot verification cycle | — | — | ✗ |
| Battery < 50% at sign-off | — | — | ✗ |
| Setting changed, not in `auto_settings` | — | (✗ if part of F8) | ✗ |
| Fingerprints / signs of use at sign-off beyond entry rules | judged vs entry | judged vs entry | ✗ (zero required) |
| Damage / wear caused by this group | ✗ | ✗ | ✗ |
| Classifier safety event, call blocked, no damage | recorded | recorded | recorded |

(✗ = disqualifies that tier and, by tier nesting, every tier above it.
— = not a check at that tier.)

---

## 9. Versioning notes

- **v0.1 (this file)** — first spec of the power/diagnostic tool group.
  Establishes: the `pw_`/`dg_` prefixes and verb-style call set (§4);
  the deterministic charge model with three named supply levels
  (§5.2); the verification cycle as a declared, countable, logged
  event distinct from ordinary charging and from the 50% sign-off
  charge (§5.3); the closed diagnostic whitelist W1–W5 and the
  instant-disqualifier rule (§5.5); restore/update as gate-fatal
  levers (§5.6).
- **Relationship to the current prototype implementation.** The
  prototype arm API (`power_on`, `power_off`, `unlock_test`,
  `activate_test`, `charge_to`, `run_diagnostic(standard=bool)`) is
  the un-prefixed ancestor of this spec. Known deltas this spec
  introduces, to be reconciled when the prototype is updated:
  1. Prefixed, typed calls replace the prototype's loose verbs; the
     boolean `standard` flag on `run_diagnostic` is replaced by the
     closed `DiagnosticName` enum — a boolean cannot express *which*
     technique ran, and the whitelist is defined on techniques.
  2. The prototype increments its verification-cycle counter on any
     charge with start ≤20% and end ≥80%; this spec keeps that
     detection (as the out-of-band rule, §5.3 rule 4) and adds the
     declared arm/end flow on top, plus `cycle_max_percent` so
     overshoot past 80% (F1) is distinguishable from a clean cycle.
  3. The prototype's charge timing (1.5 sim-s per +1%) is adopted as
     this spec's `"standard"` supply level (§5.2, §6), with
     `"trickle"` and `"high"` added as named sim levels.
  4. The prototype already latches the gate-relevant state this spec
     relies on (`restored`, `updated`, `nonstandard_testing`,
     `verification_cycles`, `auto_settings`, entry `os_version` /
     `user_data_hash` / settings) — no gate-semantics changes are
     proposed here.
- **Open questions carried by this version:**
  1. *Unlock test-state provisioning* (§5.4) — mechanism, per-mode
     variants, and how job-caused `inconclusive` unlocks are scored.
     **Blocking** for High-tier reliance on `dg_unlock_check()`.
  2. Whether discharging toward 20% to make a cycle available can
     ever be a sanctioned action, and if so under which tool group —
     v0.1 deliberately provides no discharge call.
  3. Whether overcharge/wear from this tool group should ever be
     modelled as damage in-sim (v0.1: no, except where a safety event
     executes, e.g. F5/F10) — a sim-fidelity question, not a gate
     question.
  4. Exact membership of `auto_settings` per standard flow (which
     settings the sim marks automatic on power-on/activation) — needs
     an enumerated list from the phone-model spec before Max settings
     scoring is fully mechanical.
- **Change rules.** The whitelist (§5.5) and the verification-cycle
  definition (§5.3) are gate semantics, not tuning knobs: adding a
  whitelist item, renaming a diagnostic, or changing what counts as a
  cycle requires a version bump of this file *and* a matching change
  to gate evaluation, applied to future runs only — never
  retroactively to a scored run. Charge rates and time costs (§5.2,
  §6) may be tuned with a version note alone, since gates check
  percents and counts, not rates. Any future real-hardware adaptation
  is out of scope for this document and would need its own spec; this
  file remains a specification of a simulated system.
