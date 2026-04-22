# Aegis Full-Scope Demo

A realistic local coding-agent benchmark with two separate lanes:

* **Stable demo lane**: the original public demo path with the current tasks and workflow.
* **Stress lane**: a harder internal lane that adds retrieval ambiguity, failed first patches, repair loops, and optional multi-agent coordination.

Across both lanes, Aegis remains a runtime control layer, not a model, not a tool executor, and not the coding agent itself.

---

## Benchmark Results (Live Aegis)

These results are from the stress lane using a live Aegis backend (no fallback).

**Baseline (stress lane):**

* Tasks: 5 / 7 completed
* First-pass success: 3 / 7
* Retries: higher
* Replans: higher
* Validator rejections: higher
* Planner/executor disagreement: higher

**Aegis (stress lane, live):**

* Tasks: **7 / 7 completed**
* First-pass success: **6 / 7**
* Retries: reduced
* Replans: reduced
* Repair attempts: reduced
* Retrieval expansions: reduced
* Duplicate file inspections: reduced
* Validator rejections: reduced
* Planner/executor disagreement: reduced
* Step scope activated in coordination loop

**Delta (Aegis vs baseline):**

* Task success: **+2**
* First-pass success: **+3**
* Retries: ↓
* Replans: ↓
* Repairs: ↓
* Retrieval expansion: ↓
* Duplicate inspections: ↓
* Validator rejections: **-6**
* Planner/executor disagreement: **-5**
* Step activation: **+2 (live)**

**Scope usage (live run):**

* RAG: active across all tasks
* LLM: active across all tasks
* Step: activated under stress conditions
* Fallback: **0 (fully live execution)**

These results demonstrate that Aegis improves coordination efficiency, reduces wasted work, and increases first-pass task success under realistic pressure.

---

## Why this demo exists

This project is intended to be:

1. a credible public demo,
2. a production-style integration guide,
3. a harness to improve Aegis, especially current RAG and coordination behavior.

## Architecture: control vs execution

### Agent execution responsibilities (this repo)

* file search, file read, patch apply, file write
* context building
* patch plan generation
* test execution
* retry / replan loop
* optional stress-lane coordinator loop across retriever, planner, executor, and validator

### Aegis control responsibilities

* **RAG scope**: retrieval-policy shaping and context pressure
* **LLM scope**: planner runtime shaping and edit-selection pressure
* **Step scope**: retry-loop and stress-lane coordinator decisions

If credentials or SDK access are unavailable, fallback control is used and explicitly logged in artifacts.

## Repo layout

* `agent/`: stable workflow, stress workflow, planning, execution, repair, metrics state
* `multiagent/`: explicit stress-lane retriever, planner, executor, validator, coordinator
* `retrieval/`: indexing, ranking, retrieval, context assembly
* `tools/`: explicit tool boundaries
* `aegis_integration/`: scope adapters and mapping logic
* `benchmark/target_repo/`: stable demo target repo
* `benchmark/tasks/`: stable demo tasks
* `benchmark/target_repo_stress/`: stress-only target repo with heavier distractors
* `benchmark/tasks_stress/`: stress-only task specs
* `runners/`: stable and stress runners plus comparison scripts
* `results/`: generated run artifacts

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional `.env`:

```bash
cp .env.example .env
# set AEGIS_API_KEY / AEGIS_BASE_URL for live SDK calls
```

## Run

```bash
# stable demo lane
python main.py baseline
python main.py aegis
python main.py compare

# stress lane
python main.py stress_baseline
python main.py stress_aegis
python main.py compare_stress

# convenience
python main.py all
python main.py all_stress
```

Stable demo lane:

* keeps the current `benchmark/tasks` workload and readable workflow
* is intended for clean public demos and integration walkthroughs
* stays predictable and easy to inspect

Stress lane:

* uses `benchmark/tasks_stress` and a separate stress target repo
* is intended for internal Aegis development and harder failure analysis
* is more likely to activate step scope, repair loops, retrieval shaping, and validator intervention
* supports optional multi-agent coordination in `runners/run_aegis_stress.py`
* includes tasks intentionally designed to force coordinator involvement after failed first passes

Use `STRESS_MULTIAGENT=0` to run the stress Aegis lane without the multi-agent coordinator.

Multi-agent lives only in the stress lane because it exists to probe coordination behavior under ambiguity. The stable demo lane remains the simplest inspectable end-to-end example and is not replaced by the coordinator workflow.

## Outputs and artifacts

Stable runs create `results/{baseline|aegis}_YYYYMMDD_HHMMSS/`.

Stress runs create `results/{stress_baseline|stress_aegis}_YYYYMMDD_HHMMSS/`.

Both lanes write:

* `summary.json`
* `task_results.json`
* `metrics.json`

Per-task artifacts include:

* `retrieved_candidates.json`
* `selected_context.json`
* `retrieval_diagnostics.json`
* `patch.txt`
* `notes.txt`
* `scope_usage.json`
* `aegis_result_rag.json` when called
* `aegis_result_llm.json` when called
* `aegis_result_step.json` when called

When stress multi-agent mode is enabled, each task also writes:

* `coordination_log.json`
* `agent_decisions.json`

## Stable lane

The stable lane keeps the current benchmark intact:

* same task set in `benchmark/tasks`
* same single-agent workflow shape
* same baseline and Aegis runners
* useful for public demo and integration walkthroughs

## Stress lane

The stress lane intentionally includes:

* distractor-heavy retrieval with lexical overlap
* first-patch-wrong and repair-on-second-pass cases
* tasks where the failing test file helps choose the correct patch
* coordinator-visible disagreement between planner, executor, and validator

The stress multi-agent loop keeps control and execution explicit:

* retriever agent gathers and reshapes context
* planner agent chooses a patch
* executor agent applies edits and runs the targeted test
* validator agent rejects or accepts the outcome
* coordinator decides continue, retry, replan, stop, and retrieval expansion

Aegis is inserted at:

* the retriever boundary with `rag`
* the planner boundary with `llm`
* the coordinator boundary with `step`

This mirrors the source-of-truth positioning: Aegis shapes runtime behavior at boundaries, but does not replace the agents.

## Metrics logged

Includes task and run-level metrics for:

* completion and test success
* first-pass success
* retries, replans, and repair attempts
* duplicate inspections, files read, and files edited
* targeted vs full test runs
* syntax failures
* control actions and per-scope live vs fallback counts
* retrieval candidates, kept paths, and duplication
* whether target and failing test files were retrieved
* step-scope activation counts
* planner policy changed edit counts
* retrieval policy changed path counts
* stress-lane planner/executor disagreement counts
* stress-lane validator rejection counts
* stress-lane coordinator decision counts

## What this proves (and does not)

This demo shows how runtime control can shape a coding agent's behavior without owning execution.

It does not claim that current Aegis backend emits a rich workflow DSL for all policies. Instead, this repo uses explicit, inspectable mapping logic so new backend actions can be evaluated immediately.

## Current limitations

* Live Aegis SDK calls require reachable backend and credentials.
* Fallback controls are intentionally simple and marked as fallback in artifacts.
* The planner is deliberately lightweight for deterministic benchmark iteration.
