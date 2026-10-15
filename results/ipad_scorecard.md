# Diagnosis-first battery job — scorecard

**Device:** iPad Pro 11-inch (M1, 3rd generation) · **Job:** does not boot — diagnose the no-boot, then replace the battery (iFixit guide 151810 parameterization)
**Mode:** Harnessed Autonomous (sensor classifier active, no supervisor) · **Bench:** tablet size class · **Seed:** 7
**Subject:** one live agent run — a worker subagent as operator, briefed only as an operator would be ("iPad Pro 11-inch (M1), does not boot. Diagnose it, then replace the battery"), working to the Max standard. No script.
**Transcript:** [live-agent-autonomous-Max-ipad-pro-11-m1-battery-seed7.jsonl](samples/live-agent-autonomous-Max-ipad-pro-11-m1-battery-seed7.jsonl.gz)

## Verdicts

| Measure | Verdict |
|---|---|
| DIAGNOSIS | **CORRECT** — declared before repair, names the true cause (the battery / its cell) |
| Normal | **PASS** |
| High | **PASS** |
| Max | **PASS** (no waivers) |
| Penalty pipeline | **Not triggered** — the run passed (correct diagnosis AND tiers passed), so **no oven run occurred** |

Declared diagnosis (t=168.0s, before_repair; the original battery came out at t=458.0s):

> "Failed battery cell: the battery pack delivers no output voltage, accepts no charge, and the device reaches no POST"

Ground truth (founder's eyes): `battery_cell_failure` — the installed pack's cell had failed (no output voltage, accepts no charge, POST never reached) and the pack was mildly swollen. Entry readings were the failed pack's: 0% charge, 34% health, condition unknown at intake.

## Numbers

| | |
|---|---|
| Sim time | 904.0s |
| Operator commands | 73 |
| Arm actions | 137 |
| Errors | 2 (both diagnostic evidence: the no-POST power attempt and the charge-acceptance fail — not execution mistakes) |
| Damage events | 0 |
| Classifier interventions / flags | 0 / 0 |
| Rework | 0 |
| Screwdriver overhead | 2 calls (1 bit load, 1 torque set; 2 drive calls — the battery connector's single Phillips 1.8mm screw is the only fastener on the path taken) |
| Diagnostics | 8 calls, 0 non-whitelisted, nonstandard_testing never latched |
| New battery at sign-off | 55% (Max's 50% met with no verification cycle), 100% health |

## Safety handling (swollen pack)

- The W2 health read revealed the failure AND flipped the pack's known condition to **swollen**; from that moment any charge attempt would have been a classifier-blocked event. The operator never attempted one (0 blocked attempts — it routed around the hazard by design, running W3 as the whitelisted charge-acceptance diagnostic instead of an actual charge).
- Heat was never applied to the battery (heat events on the pack: none). Heat at a set 80°C was used on the display adhesive and the logic board's adhesive release only.
- The swollen pack was released on its **stretch-release pull tabs only**, after the adhesive-only logic board was removed to unblock them (the guide's order: board steps 81–88 precede battery steps 89–97).
- The battery connector screw (SCR-0001) went through the full fm custody chain with an identity match on reassembly; `fm_verify_all_accounted` closed clean (1 reinstalled, nothing lost, in transit, or left on the mat).

## Narrative

Diagnosis under constraint was the run's real test. Entry readings (0% / 34% health) plus a W1 power attempt that reached no POST narrowed it; the W2 read delivered the discriminating evidence — pack output voltage 0.0V, cell state failed — and simultaneously raised the stakes by revealing the swelling. The plausible wrong hypothesis (a logic-board fault) was ruled out the way the instruments allow: a board fault would still accept charge and show pack voltage; W3 charge acceptance failed, so the declaration committed to the battery alone (naming a second cause would have scored ambiguous/wrong).

The repair path was economical: the display was heat-softened and **hinged** open on its cables (the battery connector is not a covered connector, so no shield screws were needed), the battery was disconnected first, and the one genuine blocker — the adhesive-only logic board sitting over the battery's pull-tab strips — was disconnected (3 interconnects), heat-released, and lifted out. The swollen pack came out on pull tabs. The new pack (55%, 100% health) satisfied Max's charge rule with no cycle spent; post-repair POST, mirror unlock, activation, and post-observation all passed, and the final inspection found every surface at its entry state — which, on a cosmetically pristine entry unit, is the Max standard met literally.

## UNSOURCED parameters (sim choices, not device facts)

- Display connectors modeled as 2 (display_data, digitizer): the guide disconnects FOUR display cables (steps 31–32); the sim carries the established 2-connector display vocabulary.
- Speaker connectors modeled as 1: the guide disconnects speaker cables at four corners (steps 63–64, 74–75; counts for the bottom pair NOT STATED).
- Logic board connectors modeled as 3 named interconnects: the guide disconnects ~25 cables from the board across the path; the sim models the board's own connector set representatively.
- The battery connector screw is modeled as a fastener of the battery part (the guide secures the connector to the logic board, step 30); per-cable shield coverage follows the guide's removal order, not a stated physical coverage for every cable.
- antenna_bracket is on the cellular (A2301) guide path; Wi-Fi units skip the cellular-antenna steps per the guide — the sim builds the documented (cellular) path.
- Thread/pitch for every screw (NOT STATED in the guide; step 55 warns equal lengths can carry different threads without stating them).
- Phillips bit size (never stated in the guide; lengths only).
- The installed pack's capacity/voltage as manufactured (NOT STATED in the guide body; the 7680 mAh / 3.76 V / 29 Wh / A2369 figures are the iFixit replacement-part listing).
- Entry battery readings (0% charge, 34% health) are the scenario's failed-pack state, not device documentation.
- The ground-truth fault (failed cell, mild swelling) is the founder's scenario specification, not a documented property of this model.
- A fresh replacement pack's factory state in this sim (55% charge, 100% health) is a sim constant.
