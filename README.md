# Aegis Full-Scope Demo

A realistic local coding-agent benchmark that compares two modes under the same workload:

- **Baseline mode**: no runtime control layer.
- **Aegis mode**: inserts Aegis control at **RAG**, **LLM**, and **step-loop** boundaries.

This repo demonstrates Aegis as a **runtime control layer**—not a model, not a tool executor, and not the coding agent itself.

## Why this demo exists

This project is intended to be:

1. a credible public demo,
2. a production-style integration guide,
3. a harness to improve Aegis (especially current RAG scope behavior).

## Architecture: control vs execution

### Agent execution responsibilities (this repo)

- file search, file read, patch apply, file write
- context building
- patch plan generation (model adapter)
- test execution
- retry / replan loop

### Aegis control responsibilities

- **RAG scope** (`client.auto().rag(query=..., retrieved_context=..., symptoms=..., severity=..., metadata=...)`): retrieval-policy shaping and context pressure.
- **LLM scope** (`client.auto().llm(base_prompt=..., symptoms=..., severity=..., input=..., metadata=...)`): planner runtime shaping (strictness/selection knobs).
- **Step scope** (`client.auto().step(step_name=..., step_input=..., symptoms=..., severity=..., metadata=...)`): retry-loop policy decisions.

If credentials/SDK are unavailable, fallback control is used and explicitly logged in artifacts.

## Repo layout

- `agent/`: workflow, planning, execution, repair, metrics state
- `retrieval/`: indexing, ranking, retrieval, context assembly
- `tools/`: explicit tool boundaries (`file_search`, `file_read`, `file_write`, `patch_apply`, `test_runner`)
- `aegis_integration/`: scope adapters and mapping logic
- `benchmark/target_repo/`: tiny Python repo with intentional bugs + distractor files
- `benchmark/tasks/`: task specs with realistic bugfix objectives
- `runners/`: baseline, aegis, and comparison scripts
- `results/`: generated run artifacts

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
python main.py baseline
python main.py aegis
python main.py compare
# or
python main.py all
```

## Outputs and artifacts

Each run creates `results/{baseline|aegis}_YYYYMMDD_HHMMSS/` with:

- `summary.json` (includes per-scope live vs fallback counts)
- `task_results.json` (includes per-task scope usage through task metrics)
- `metrics.json`

Per-task artifacts (`tasks/<task_id>/`) include:

- `retrieved_candidates.json`
- `selected_context.json`
- `patch.txt`
- `notes.txt`
- `aegis_result_rag.json` (Aegis mode)
- `aegis_result_llm.json` (Aegis mode)
- `aegis_result_step.json` (Aegis mode)

## Control mapping behavior

- **RAG policy mapping** supports keep-k changes, path boosts, required target/test inclusion, src/test preference, and dedupe aggressiveness.
- **LLM policy mapping** shapes planner strictness (`strict_old_snippet_match`), max candidate edits, minimal vs broader patch preference, test-context weighting, and repair mode.
- **Step policy mapping** supports retry/replan/stop plus loop policies (targeted-only reruns, touched-file reread mode, duplicate-read suppression, and retrieval size adjustment on retry).

## Benchmark stress cases now included

Tasks intentionally include:

- distractor files with high lexical overlap (`src/noisy_reference.py`)
- target-vs-distractor ambiguity
- retrieval noise and duplication pressure
- a repair-path task that requires a second attempt (`task_005_support_routing` uses `repair_hints`)

## Metrics logged

Includes task and run-level metrics for:

- completion / tests
- llm calls / retries / replans / repair attempts
- duplicate inspections / files read / files edited
- targeted vs full test runs
- syntax failures
- control actions and per-scope action counts
- per-scope live vs fallback counts
- retrieval candidates / kept / duplication
- whether relevant source and failing test files were retrieved

## What this proves (and does not)

This demo shows how runtime control can shape a coding agent’s behavior without owning execution.

It does **not** claim that current Aegis backend emits a rich workflow DSL for all policies; instead, this repo uses explicit, inspectable mapping logic so new backend actions can be evaluated immediately.

## Current limitations and TODOs

- Live Aegis SDK calls require reachable backend + credentials.
- Fallback controls are intentionally simple and marked as fallback in artifacts.
- Model adapter is deliberately lightweight for deterministic benchmark iteration; swap with a production model adapter while keeping control boundaries intact.
