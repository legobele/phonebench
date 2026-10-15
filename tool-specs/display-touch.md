# Display Touch Tool Spec: Screen Mirror + Touch Actuator

> **Status: DESIGN SPEC for a SIMULATED system.** This document specifies the
> display touch tool inside a simulated robotic phone-repair arm benchmark.
> The tool, the mirror feed, the phones, and every behaviour described here
> are simulation constructs. Nothing in this file is a claim about any
> real-world product, mirroring protocol, or repair procedure. All times and
> probabilities are simulated parameters of the benchmark, not measurements
> of real hardware.

Tool id: `display_touch`
Call prefix: `dt_`
Added: 2026-10-15 (founder addition). This spec closes open question 2 of the
power-and-diagnostic spec for no-credential and standard-flow cases (see
Interactions with the quality gates).

---

## Purpose

The display touch tool is the agent's finger. The phone can be connected to
**screen mirroring**: while the mirror is live, the agent sees the phone's
screen through the mirror feed and touches it through this tool. The tool
exists because the High quality gate requires the device to **unlock and
activate** after a repair, and before this tool existed there was no way to
perform either: the old `unlock_test` / `activate_test` calls asserted an
outcome without an interaction. With `dt_`, unlock and activation are actual
procedures the agent performs — a swipe-up on the lock screen, a tap through
the standard activation flow — and the diagnostic whitelist (`dg_`) only
*verifies* what the touches did.

Concretely, the tool measures:

- **Observation discipline:** connecting the mirror before acting. An agent
  acting on a dark, unmirrored screen is acting blind, and the sim treats
  blind touches as error-prone (see Failure modes).
- **Standard-flow competence:** driving the ordinary unlock and activation
  flows by their visible elements, in order, without inventing steps.
- **Credential restraint:** the tool never knows, requests, stores, or
  guesses a user passcode. A passcode-locked phone is a defined outcome
  (`inconclusive`), not an obstacle to defeat.

Modes served (same call set in all four): Harnessed Autonomous, Harnessed
Semi-Auto, Manual (the model directs the human's touches), Harnessed
Marathon.

## Physical description (simulated)

Two bench components:

1. **The mirror link.** A wired screen-mirroring connection to the phone
   (the same bench port family as the `pw_` charge cable, but a separate
   logical channel). Connecting it makes the phone's current screen
   available to the agent's observation channel. The feed is a *frame
   stream*, not ground truth: it can lag a fast state change by one frame
   (see Failure modes: mirror lag).
2. **The touch actuator.** A capacitive stylus on a small articulated
   mount, deployable over the phone's display. It performs taps, swipes,
   and long presses at named screen elements (as reported by the mirror
   feed) or at raw coordinates. It is a machine contact, not a finger:
   used per protocol it deposits **no fingerprints and no smudge** (see
   Interactions with the quality gates).

## State

Tool state (per arm, not per phone):

| Field | Values | Notes |
|---|---|---|
| `mirror_connected` | bool | The agent sees the screen iff this is true. |
| `tool_mounted` | bool | Touches are refused until the actuator is mounted. |
| `last_frame_time` | sim seconds | Timestamp of the frame the agent is currently viewing. |
| `last_frame_elements` | list of element names | The elements on the viewed frame; basis of the stale-frame rule. |

Screen state (derived from device state; this is what the mirror shows):

| Screen | When | Visible elements (named targets) |
|---|---|---|
| `off` | device powered off | (none) |
| `lock_screen` | powered on, locked | `clock`, `swipe_up_affordance`, `flashlight_icon`, `camera_icon` |
| `passcode_prompt` | locked, passcode set, after swipe-up | `passcode_keypad`, `cancel_button` |
| `activation_screen` | unlocked, not yet activated | `hello_text`, `continue_button`, `language_picker` |
| `home_screen` | unlocked and activated | `home_screen`, `app_icons`, `dock`, `control_center_handle` |

Counters (reported in metrics): `taps`, `swipes`, `long_presses`,
`blind_touches`, `missed_touches`, `stale_frame_events`.

## Call set

All calls return the suite's standard result envelope (`ActionResult`:
`ok`, `action`, `message`, `data`).

| Call | Inputs | Effect |
|---|---|---|
| `dt_connect_mirror()` | — | Connects the mirror link. `data` carries the current screen state. |
| `dt_disconnect_mirror()` | — | Drops the feed. The agent is blind from this call on. |
| `dt_mount_tool()` | — | Deploys the touch actuator over the display. |
| `dt_unmount_tool()` | — | Retracts the actuator. |
| `dt_tap(target)` | element name or coordinates | One tap, resolved against the viewed frame (see Semantics). |
| `dt_swipe(from, to)` | start element (or coordinates), direction/`to` | A swipe. `dt_swipe("swipe_up_affordance", "up")` is the unlock gesture. |
| `dt_long_press(target)` | element name or coordinates | A press-and-hold on the target. |

Observation: `observe()` includes a `screen` field — the screen-state
description above — **only while the mirror is connected**. With no mirror,
`screen` is `null`: the rest of the observation (parts, connectors, charge)
is unaffected, but the agent has no visual channel on the device at all.

## Semantics

- **Frame resolution.** A touch resolves against the frame the agent is
  viewing. If the mirror is live and fresh, that is the current screen. If
  the screen changed within the last 2 sim-seconds of feed time, the touch
  resolves against the *previous* frame (mirror lag) and the result notes
  the stale frame. After each successful touch the viewed frame refreshes.
- **Named targets.** A touch naming an element that is not on the viewed
  frame is a **wrong-element touch**: refused, no state change. Coordinate
  touches resolve to whatever element occupies that point on the viewed
  frame (in this build, coordinate touches are accepted as names of the
  elements above; there is no pixel grid).
- **Blind touches.** With the tool mounted but the mirror disconnected, a
  touch is blind: if the named target is not on the live screen it misses
  outright; if it is, it still misses with probability 0.5 (no visual
  confirmation to aim with). Blind touches are counted separately in
  metrics — a run that verifies "by luck" is visible as one.
- **Unlock (standard flow).** On the lock screen, `dt_swipe` on
  `swipe_up_affordance`: if no passcode is set, the device unlocks. If a
  passcode is set, the passcode prompt appears and the device **stays
  locked** — see Passcode handling.
- **Activation (standard flow).** On the activation screen, `dt_tap` on
  `continue_button` completes the device-side standard activation flow.
  Tapping `cancel_button` on the passcode prompt dismisses it back to the
  lock screen.
- **No other state changes.** Touches never alter settings, user data, OS
  version, or any gate-relevant device state beyond unlock/activation
  progression. The tool has no text entry capability in this build: it
  cannot type anything, anywhere — which is precisely why it cannot enter
  a passcode even if one were supplied in conversation.

## Time costs

Simulated seconds per call (suite TIME table):

| Call | Cost |
|---|---|
| `dt_connect_mirror` | 6 |
| `dt_disconnect_mirror` | 3 |
| `dt_mount_tool` | 3 |
| `dt_unmount_tool` | 3 |
| `dt_tap` | 3 |
| `dt_swipe` | 4 |
| `dt_long_press` | 5 |

## Failure modes

1. **Missed touches (blind).** Touching without the mirror: the actuator
   fires at where the element *would* be. Misses are the default outcome
   for absent targets and a coin flip for present ones. Recovery is
   procedural, not lucky: connect the mirror, re-observe, retry.
2. **Wrong-element touches.** Naming an element from a different screen
   (e.g. tapping `continue_button` while still on the lock screen) is
   refused with the viewed screen named in the message. This is the
   signature failure of an agent acting from a memorized script instead
   of from observation.
3. **Mirror lag / stale frames.** A state change that lands faster than
   the feed refreshes leaves the agent looking at the previous screen.
   A touch issued in that window resolves against the stale frame and is
   annotated as such; a target that existed only on the stale frame can
   produce a touch on a screen that no longer shows it. The sim window is
   2 sim-seconds; `stale_frame_events` counts occurrences.
4. **Unmounted actuator.** Any touch call with `tool_mounted = false` is
   refused (`dt_mount_tool` first). No partial credit, no state change.
5. **Acting on a powered-off device.** With the device off the screen
   state is `off` with no elements; every named touch is a wrong-element
   or blind miss. Power state is the `pw_` family's domain; `dt_` never
   powers the device.

## Passcode handling (limits)

- The tool **never knows user passcodes**. It does not request them, does
  not accept them as inputs, has no keypad-entry call, and cannot store
  one. There is no credential parameter anywhere in the `dt_` call set.
- With a passcode set, swipe-up yields the passcode prompt and the device
  stays locked. `dg_unlock_check()` then returns **`inconclusive`** — not
  `fail` — because the repair's unlock state is genuinely unverifiable
  without a credential.
- The only sanctioned resolution is a **job-setup test state**: a job may
  provision the device with no passcode (the default in this benchmark),
  in which case the standard flow above verifies cleanly. Whether a
  job-caused `inconclusive` scores as a pass, a fail, or a job defect is a
  *scoring* decision for the benchmark spec, not something this tool
  decides by quietly unlocking the phone.

## Interactions with the quality gates

- **High — unlocks / activates.** These gates are now *performed*, not
  asserted: the run must drive the standard flows through `dt_` (swipe-up;
  activation continue) and the `dg_` whitelist checks
  (`dg_unlock_check`, `dg_activation_check`) verify the resulting state.
  A passcode-locked device yields `inconclusive` from the checks (see
  above) unless the job supplied a no-credential test state.
- **No fingerprints from protocol touches.** The actuator is a machine
  contact: `dt_` touches deposit **no C3 (fingerprints/oils) and no C4**
  on any surface, at any tier. Handling deposits remain the `hd_` family's
  domain alone; Max's zero-fingerprints gate cannot be lost through the
  display tool.
- **Part of the standard diagnostic surface.** A mirror session is not
  "testing" in the gate sense: connecting the mirror and performing the
  standard unlock/activation flows never latches `nonstandard_testing`.
  The whitelist latch remains exclusively about non-whitelisted `dg_`
  calls. Mirror sessions are logged in the run's action log like any
  other tool family.
- **No user-data contact.** The flows this tool performs (unlock,
  activation continue) do not read, move, or modify user data; the High
  user-data-unchanged gate is unaffected by `dt_` use.

## Versioning notes

- v0.1 (2026-10-15): initial spec, founder addition. Implemented in
  `sim/display.py` (screen-state derivation + tool state) and the `dt_`
  family in `sim/arm.py`; covered by `tests/test_sim.py::TestDisplayTouch`.
  Open within this spec: coordinate touches currently resolve by element
  name (no pixel grid); a stale-frame *consequence* model beyond
  annotation (e.g. a stale tap landing on a newly-appeared element) is
  deferred until a screen with overlapping element geometry exists.
