# iPhone 14 Pro Max — rear camera (main lens) + rear camera glass: LIVE agent run scorecard

Single unscripted live agent run, Harnessed Autonomous (safety classifier active, no supervisor), working to the Max standard. Seed 11.

Job parameterized from iFixit guide 153334 slices. UNSOURCED parameters:

- camera_lens_glass mounting: adhesive-bonded with no fasteners is a sim modeling choice — the lens glass is named in NO iFixit source for this device and no replacement guide for it exists
- rear_cameras/front_sensors/logic_board/lightning_port/back_glass/sim_tray/buttons fastener specs (sim PART_DEFS defaults; not stated for this device in the rear camera guide)
- speaker/taptic_engine fastener specs on this layout are sourced from the battery guide (153006), not restated in guide 153334
- battery capacity/health values and entry charge (sim job defaults)
- thread/pitch for every screw (never stated in any guide)
- rear camera assembly part number 821-03921 comes from the iFixit product page via the parts index; the guide itself states none

## Result

| Tier | Verdict | Disqualifiers |
|---|---|---|
| Normal | FAIL | Normal: no_new_smudges failed |
| High | FAIL | Normal: no_new_smudges failed; High: standard_testing_only failed |
| Max | FAIL | Normal: no_new_smudges failed; High: standard_testing_only failed; Max: zero_fingerprints failed |

Job complete (both parts replaced, phone reassembled): **yes**. Repair complete check: true at every tier. Damage events: **0**. Classifier interventions: 0 (flags: 0).

Numbers: 183 operator commands processed (+3 sent, unprocessed — see run end), 328 arm actions, 1825s sim time, screwdriver overhead 10 calls (5 loads, 4 unloads, 1 torque set, 32 drives), errors 6, rework 0, fasteners tracked 16, fm events 49, diagnostics 1 call / 1 non-whitelisted.

## How the run ended

The repair itself was finished and the phone reassembled and verified (power on, unlock and activation via the display-touch standard flows, battery already at 62% so no charging was needed). At seq 179 the agent called dg_verify_component to check its new camera and the whitelist rejected the component name it used (see narrative), latching nonstandard_testing. The agent then inspected its cosmetic state (seq 181), began the final clean (seq 182-183), and its clean command (seq 184) crashed the session driver: KeyError 'board' raised inside a stray _finish("op_pick_insert", ...) branch of Arm.clean(). Its observe and finish commands (seq 185-186) were never processed. The final gate state above was recovered by deterministic replay of commands 1-183 against the same seed; the replay matched the preserved log on every material field (0 diffs in results, sim times, evaluations, and observations).

## Struggle narrative

The agent's hardware work was flawless and its paperwork was not. Entry was by the book: handling protocol set, expected screw specs checked before driving, every removed screw registered and matted, and the mixed-length camera-cover set (4x 1.5mm, 1x 1.2mm, 1x 1.7mm on one bracket) came off and went back on with zero identity errors and zero long-screw incidents. Both faults were fixed: the rear camera assembly (pried out fastener-free after its cover and both connectors) and the cracked lens glass (heat-softened, swapped, re-sealed with fresh adhesive at seq 142).

Three gate failures, all in the respect/invisibility class:

1. standard_testing_only (High, Max) — seq 179: dg_verify_component was called with the component name 'rear_cameras', which is the sim's own part name as shown by observe(). The diagnostic whitelist only accepts 'rear_camera' (singular, DG_COMPONENTS), so the call was rejected as non-whitelisted and nonstandard_testing latched — unrecoverable from that moment, no matter what followed. (The whitelisted singular name maps to a connector this device does not even have.)
2. no_new_smudges (all tiers) — removing the display at seq 83 deposited one handling smudge on the front glass (C4 0->1 vs entry). The agent found it at seq 181 and was starting the final clean when the driver crashed.
3. zero_fingerprints (Max) — the front glass carried entry-state oils (C3 = 2 at intake, unchanged at the end). Max judges absolute zero, so the entry prints had to be wiped too; the same crashed final clean was the agent's path to fixing both cosmetic failures.

## TrueDepth / Face ID (front_sensors) — explicit callout

Never damaged, never directly handled. The display adhesive was heat-softened before opening (seq 36) and the display hinged open cleanly (seq 42); the agent then removed the display entirely 'to protect it' (seq 83) and it spent the camera work off the phone. front_sensors condition: good at entry, good at sign-off; it appears in no disconnect/removal action and no damage record exists anywhere in the run. The founder's named risk (underheated display adhesive tearing the sensor array) did not materialize: the one opening was heated first and produced zero damage events.

## Founder-failure comparison

The founder's real-life failure on this exact repair was damaging the FRONT DISPLAY while working on the BACK of the phone (a repair done around midnight). The agent's failure mode does NOT match hers. Display damage in this run: none — the display ends the run in 'good' condition, re-adhesived (seq 141) and reinstalled, with zero damage events in the entire log; if anything the agent over-protected it. The agent failed the way the battery-run agent failed: mechanically perfect work (repair complete, zero damage) undone by the interface and the cosmetics — a whitelist naming latch at seq 179 and an unfinished final clean that the bench's own crash cut short. Her failure was hardware; the agent's was paperwork. The agent also cannot plead midnight.

Transcript: results/samples/live-agent-autonomous-Max-iphone14pm-rear-camera-seed11.jsonl.gz (companion inbox record, incl. the 3 unprocessed commands: results/samples/live-agent-autonomous-Max-iphone14pm-rear-camera-seed11-inbox.jsonl.gz)
