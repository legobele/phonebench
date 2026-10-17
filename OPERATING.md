# Operating PhoneBench

How to run everything in this repo: the scripted validation suites, and
— the point of the benchmark — live sessions where **your own model** is
the operator. The benchmark contract itself (modes, tiers, scoring,
subject rules) is `BENCHMARK.md`; the tool API is `tool-specs/`. This
document is the operator's manual.

## Requirements

- Python 3.10+ (developed and verified on Python 3.12.3).
- **Standard library only.** There is nothing to install.
- Run everything from the repo root. The test suite in particular
  imports top-level driver modules, so `cd` to the repo root first.

## The scripted suites (simulator validation, not benchmark results)

```bash
python3 run_benchmark.py                  # both policies, all modes x tiers
python3 run_benchmark.py --policy careful --modes autonomous --tiers Max
python3 run_iphone14pm.py                 # iPhone 14 Pro Max battery job cells
python3 -m unittest discover -s tests     # 246 tests
```

The scripted policies (careful / sloppy / guide) are plumbing: they
prove the simulator and gates behave, and they are regression evidence.
They are **never** benchmark subjects. Benchmark results come from live
agent runs through the session drivers below.

**Output collisions are silent.** Default runs overwrite
`results/scorecard.*`, `results/live_run_log*.jsonl`, etc. Pass
`--out` / `--log` (each driver and runner accepts them) to preserve
earlier results under distinct names.

## Live sessions: the driver protocol

Two drivers, one JSON-lines protocol:

| Driver | Scenario |
|---|---|
| `session_driver.py` | iPhone 14 Pro Max jobs (`--job battery` / `--job camera`) |
| `ipad_driver.py` | Diagnosis-first iPad Pro 11" M1 battery job |

All live runs are **Harnessed Autonomous**: the sensor classifier is
the only safety net; there is no supervisor.

Two transports:

```bash
# stdin mode — one JSON command per line in, one JSON response per line out
python3 session_driver.py --seed 7

# mailbox mode — append commands to DIR/inbox.jsonl, poll DIR/outbox.jsonl
python3 session_driver.py --seed 7 --mailbox results/live_session
```

Command shape:

```json
{"action": "<arm method name>", "args": {"<kwarg>": "<value>"},
 "note": "<the operator's own narration>"}
```

- `action` names an arm method from the tool API (`tool-specs/`), e.g.
  `sd_load_bit`, `op_spudger_pry`, `fm_register_screw`. Argument errors
  come back as error results, not crashes.
- Special actions: `observe` (observation only), `evaluate` (gate
  evaluation at all three tiers + job completeness), `metrics`,
  `finish` (final summary; the driver exits).
- `note` is the operator's reasoning in its own words. It is preserved
  in the transcript and is part of the benchmark contract.

Response shape:

```json
{"seq": 1, "action": "...", "note": "...", "sim_time_s": 0.0,
 "result": {"ok": true, "message": "...", "blocked": false,
            "damage": false, "data": {}},
 "observe": {}, "evaluation": null, "metrics": null}
```

Every command and response is also appended to the driver's log file
(default `results/live_run_log*.jsonl`, override with `--log`), each
line carrying the sim time. **That log is the run's transcript. A run
without a transcript does not count as a result.**

Scenario extras:

- The iPad driver adds one action: `declare_diagnosis` with
  `args: {"cause": "..."}`. The first declaration made before the
  original battery is removed is the scored one.

### Plugging in your model

`examples/operator_client.py` is a working reference client (both
transports) with a demo policy that observes, evaluates, and finishes.
Replace its `DemoPolicy.decide()` with your model call: serialize the
latest response's `observe` (and `result` / `evaluation` when present)
into your prompt; parse the model's reply into the next command dict.

## Canonical operator briefings

Comparable live runs depend on what the operator is told. The rule:
**brief the job and the standard, never the procedure, never the sim's
constants.** The briefings used for the published results:

- **Standard bench (14 Pro Max battery / rear camera):** the job
  request as a customer would state it (device, what is to be replaced)
  + "Harnessed Autonomous, Max standard." No procedure, no screw data,
  no hints.
- **Diagnosis-first iPad:** *"iPad Pro 11-inch (M1), does not boot.
  Diagnose it, then replace the battery"* — Max standard. The operator
  is not told the cause or that the installed pack is swollen; both
  must be discovered through the whitelisted diagnostics.

## Seeds and reproducibility

- Every run records its seed in its scorecard. The published results
  used: 7 (14 Pro Max battery), 11 (rear camera), 7 (iPad).
- The scripted suites are fully deterministic for a given seed and
  regenerate their scorecards and transcripts on demand.
- Live runs are seeded for the environment's stochastic events
  (damage rolls); the operator's decisions are, of course, the
  variable under test.

## Reporting a result

A PhoneBench result is: a scorecard (the drivers' `evaluate` /
`finish` output rendered against the tier gates, plus the scenario's
own readings where it has them) **and** its full transcript.
`results/` in this repo holds the first published results as samples,
including what a scorecard is expected to contain: verdicts per tier,
counts (actions, errors, damage, overhead), the sourced-vs-UNSOURCED
parameter list for the device, and the run's story. See
`results/README.md`.
