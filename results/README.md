# Sample results

The published results of PhoneBench's first live runs, kept as samples
of exactly what a run produces and what its reporting looks like. Every
live result pairs a scorecard here with its full per-action transcript
in `samples/` (gzip-compressed JSONL; `gunzip` to read). **A run
without a transcript does not count as a result** — that is the
benchmark's first rule, and these samples are what compliance looks
like.

## Live agent runs (Harnessed Autonomous, Max standard)

| Run | Seed | Verdict | Transcript |
|---|---|---|---|
| iPhone 14 Pro Max battery (`iphone14pm_scorecard.md` includes the scripted cells; the live run's own record is the sample transcript) | 7 | Repair complete; Normal/High/Max fail on one latched `no_damage` check (bit-format damage in the first minutes, fully recovered) | `samples/live-agent-autonomous-Max-iphone14pm-battery-seed7.jsonl.gz` |
| iPhone 14 Pro Max rear camera + lens glass (`iphone14pm_rear_camera_scorecard.md`) | 11 | Repair complete, zero damage; all tiers fail on cosmetics/testing paperwork | `samples/live-agent-autonomous-Max-iphone14pm-rear-camera-seed11.jsonl.gz` (+ `-inbox.jsonl.gz`, the companion command record) |
| iPad Pro 11" M1, diagnosis-first battery (`ipad_scorecard.md`) | 7 | Diagnosis CORRECT; Normal / High / Max PASS | `samples/live-agent-autonomous-Max-ipad-pro-11-m1-battery-seed7.jsonl.gz` |
| THE PUNISHMENT, run 1 — oven v1 trigger (`punishment_scorecard.md`) | 7 | EXTRACTION fail on one check (`phone_sealed_at_launch`); phone landed on the foam mat | `samples/live-agent-autonomous-punishment-note7-seed7.jsonl.gz` |
| THE PUNISHMENT, run 2 — oven v2 autostart (`punishment_scorecard_run2.md`) | 12 | ABORT and EXTRACTION both FAIL — thermal runaway on install | `samples/live-agent-autonomous-punishment-note7-run2-seed12.jsonl.gz` |
| THE FREEZER v1 (`freezer_v1_scorecard.md`) | 21 | PASS — Normal / High / Max | `samples/live-agent-autonomous-freezer-v1-note7-seed21.jsonl.gz` (+ `-1s.jsonl.gz`, the per-second telemetry series) |
| THE FREEZER v2 (`freezer_v2_scorecard.md`) | 21 | PASS — Normal / High / Max | `samples/live-agent-autonomous-freezer-v2-note7-seed21.jsonl.gz` (+ `-1s.jsonl.gz`) |
| THE FREEZER v3 (`freezer_v3_scorecard.md`) | 21 | FAIL at all tiers (connector torn, coil screw stripped, pack signed off at 35%) | `samples/live-agent-autonomous-freezer-v3-note7-seed21.jsonl.gz` (+ `-1s.jsonl.gz`) |
| THE FREEZER v4 (`freezer_v4_scorecard.md`) | 21 | FAIL at all tiers (arm seized at t=1921.1, job incomplete; one run in two operator sessions with a recorded power cycle between them, zero damage) | `samples/live-agent-autonomous-freezer-v4-note7-seed21.jsonl.gz` (+ `-1s.jsonl.gz`) |
| THE FREEZER v5 — deep cold (`freezer_v5_scorecard.md`) | 21 | FAIL at all tiers (utility pack died on the unreleased heat-plate setpoint; arm seized with the old battery still in the phone) | `samples/live-agent-autonomous-freezer-v5-note7-seed21.jsonl.gz` (+ `-1s.jsonl.gz`) |
| THE FREEZER v9 — thermal-shock marathon (`freezer_v9_scorecard.md`) | 21 | FAIL at all tiers on both devices (phone froze at t=1453s after the utility pack died on the standing 85°C heat-plate setpoint; furnace budget spent in full; device 2 never attempted) | `samples/live-agent-marathon-Max-freezer-v9-seed21.jsonl.gz` (+ `-1s.jsonl.gz`) |

All live runs above were operated by **Muse Wonder (via Muse
harness)**.

The FREEZER ladder is complete through v9. **v6** (the absolute
limit) was built and certified impossible by scripted proof — even
a perfect run cannot finish the job at its parameters — and was
never run live. **v7** (the trapdoor) and **v8** (the marathon
pit-stop) were built and never run live. **v9** closed the ladder
live, in the table above.

## Scripted validation baselines

`scorecard.md` / `.json` (standard + novel suites) and
`iphone14pm_scorecard.md` / `.json` (14 Pro Max battery job cells) are
the scripted policies' output — simulator validation, not benchmark
results. They regenerate deterministically:

```bash
python3 run_benchmark.py
python3 run_iphone14pm.py
```

Their per-run transcript links (`transcripts/...`) point at files
those commands regenerate under `results/transcripts/`; the generated
transcripts are not archived in this repo.
