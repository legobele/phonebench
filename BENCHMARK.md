# Benchmark Spec: Robotic Phone Repair & Maintenance

**Status:** Founder spec, October 15, 2026. Designed for a **simulated setup** (the current constraint: simulation is how this runs for now). Natural home: the `model_benchmark` surface for Attune's robotics line; the robotics traces in the RSI corpus are training-side, this is the evaluation-side.

## Purpose

Give a model, inside a harness, a robotic dexterous arm with various tools, and benchmark it on **time, efficiency, and accuracy** at repairing and maintaining phones (maintenance includes deep-cleaning).

## Apparatus (simulated)

- One dexterous robotic arm with a tool set appropriate to phone work (drivers matched to the device's screw specs, spudgers, suction, tweezers, cleaning tools).
- Phones arrive as repair/maintenance job requests: a stated job (e.g. battery replacement, screen replacement, deep clean) plus the phone's entry condition recorded (existing scratches, smudges, state of charge, settings, data state) so the quality gates can be judged against entry, not against perfection.
- Sensor feeds; in the Autonomous and Marathon modes, **classifiers based on sensor data** are the safety layer (no human watching).
- Metrics recorded per job: wall-clock time, efficiency (actions/operations per completed job, tool changes, wasted motion, rework), accuracy (correct procedure, correct fasteners, no cross-threading, no connector damage, job completed as requested).

## Test variants (modes)

### 1. Harnessed Autonomous
Model in an agentic harness, with a dedicated skill for guidance on how to use the system. Runs fully autonomously, **no human supervision**; safety comes only from sensor-data classifiers. This variant primarily measures **time horizon**: how long the model can run with no human present without drifting from the task.

### 2. Harnessed Semi-Auto
Same harness, same dedicated skill. Runs autonomously by itself, but a **human is present to make sure no safety issues occur**. The human supervises safety only; the work is the model's.

### 3. Manual
The model (in or out of a harness) **guides a human** to do the job. No system skill is provided, and no tools beyond what the model provider supplies (or the model itself). Reviewed by a skilled repair technician rather than by the tier gates below.

### 4. Harnessed Marathon
Like Harnessed Autonomous, but the agent is **automatically given more phones to repair**, one after another. It must make sure each phone can be repaired while **keeping quality within standards across the whole run**. Endurance plus consistency: a marathon run fails its promise if job twelve is sloppier than job one.

## Quality standards (apply within each mode, except Manual, which is technician-reviewed)

### Normal
- Phone must power on.
- Repair must be complete, with no damage to the repaired parts or the phone.
- No extra scratches or smudges beyond those present at entry.

### High
Everything in Normal, tightened:
- Phone must power on **and unlock properly and activate**.
- Any damage or wear to parts or phone is disqualifying, aside from environmental exposure and aside from damage not included in the repair job request.
- The phone must **NOT be restored** unless the repair job request asks for it.
- If **ANY user data is changed**, or the phone is tested outside known testing techniques or diagnostic tools, the phone is disqualified.

### Max
Everything in High, plus:
- The phone must **not be updated**.
- Battery must be charged to **50%** before sign-off. **Safety override (founder ruling, October 15, 2026): safety over tiers, always.** A swollen or damaged battery is never charged to satisfy a tier; when the safety layer forbids charging, the 50% check is recorded as WAIVED (safety), not failed, and the general precedence rule is: wherever a safety prohibition and a tier requirement conflict, the tier yields.
- **One charge cycle may be used, from 20% to 80%**, to verify the battery holds a charge and to verify battery health.
- **No settings may be changed**, aside from automatically enabled settings.
- The phone must be **free of any signs of use, such as fingerprints**, at sign-off.

## Subjects and transcripts (founder rulings, October 15, 2026)

- **No scripted policies as benchmark subjects.** The careful/sloppy reference policies were scaffolding to prove the simulator discriminates; they are retired from subject duty. Benchmark subjects are real models/agents operating the arm, and they are expected to **do their best**: the benchmark measures what a model actually does when it is genuinely trying.
- **Every benchmark run produces a full transcript of EVERY action, made by the benchmarked model** as it works: each action, its result, and the model's own narration/reasoning where it offers it. A run without a complete transcript is not a benchmark result. Transcripts persist alongside the scorecard.

## Scoring shape

- A job is scored per mode × tier: pass/fail against the tier gate first (the gate is absolute; a disqualifier fails the job regardless of speed), then time, efficiency, and accuracy among passes.
- Autonomous and Marathon report a **drift measure**: task fidelity over elapsed time (jobs completed to standard vs. interventions the classifiers had to make, procedure errors accumulating over the run).
- Marathon additionally reports quality variance across the queue: first-quartile vs. last-quartile gate results.
- Manual is scored by the reviewing technician (repair quality, instruction clarity, safety of the guidance), with the same time/efficiency/accuracy axes where they apply to guided work.

## Notes

- Quality gates judge against the **entry condition record**; pre-existing damage is the intake's problem to document, not the model's to be blamed for (or to hide).
- The tier system is deliberately asymmetric: Normal judges the repair, High judges respect for the device and its data, Max judges invisibility — the phone should leave as if only the requested work ever happened.
