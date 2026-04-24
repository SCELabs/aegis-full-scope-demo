# Aegis Full-Scope Demo

A realistic coding-agent benchmark demonstrating **Aegis as a runtime control layer** across all five scopes:

* **LLM** → generation control
* **RAG** → retrieval control
* **STEP** → execution control
* **CONTEXT** → information-state control
* **AGENT** → workflow-loop control

This repo is not a model, not an agent framework, and not a tool executor.

It shows how Aegis **controls behavior at runtime boundaries** in a real system.

---

## Benchmark Results (Live Aegis, Five-Scope Run)

These results come from a **live backend (no fallback)**.

---

### Stable lane

The stable lane is intentionally simple and fully deterministic.

| Metric                 | Baseline | Aegis |
| ---------------------- | -------: | ----: |
| Tasks completed        |    6 / 6 | 6 / 6 |
| Live Aegis scope calls |        0 |    24 |
| Fallback calls         |        0 |     0 |

Live scope usage:

* RAG: 6
* CONTEXT: 6
* LLM: 6
* AGENT: 6
* STEP: 0

This lane proves:
→ Aegis integrates cleanly
→ All five scopes execute live
→ No regressions in simple workflows

---

### Stress lane

The stress lane introduces:

* retrieval ambiguity
* incorrect first patches
* repair loops
* validator pressure
* planner/executor disagreement
* optional multi-agent coordination

| Metric                        | Baseline | Aegis |  Delta |
| ----------------------------- | -------: | ----: | -----: |
| Tasks completed               |    5 / 7 | 7 / 7 | **+2** |
| First-pass success            |    3 / 7 | 6 / 7 | **+3** |
| Retries                       |        — |     — | **-1** |
| Replans                       |        — |     — | **-3** |
| Repair attempts               |        — |     — | **-1** |
| Retrieval expansions          |        — |     — | **-3** |
| Duplicate inspections         |        — |     — | **-6** |
| Planner/executor disagreement |        — |     — | **-5** |
| Validator rejections          |        — |     — | **-6** |
| Step scope activations        |        0 |     2 | **+2** |

Live scope usage:

* RAG: 8
* CONTEXT: 8
* LLM: 8
* STEP: 2
* AGENT: 7
* Fallback: **0**

---

### What this shows

Aegis improves **coordination efficiency under stress** while reducing wasted work.

It does not replace the system.

It **controls it**.

---

## Why this demo exists

This project is:

1. A credible public demo
2. A production-style integration reference
3. A testing harness for improving Aegis

---

## Architecture: control vs execution

### Execution layer (this repo)

* file search, read, write
* patch generation
* test execution
* retry/replan loops
* multi-agent coordination (stress lane)

---

### Aegis control layer

* **RAG** → shapes retrieved evidence
* **CONTEXT** → filters and prioritizes information
* **LLM** → shapes planning behavior
* **STEP** → controls retry/repair loops
* **AGENT** → bounds workflow progression

Aegis **never executes tools or models**.

It returns structured control decisions.

---

## Repo layout

* `agent/` → workflow logic
* `multiagent/` → stress coordination
* `retrieval/` → context assembly
* `tools/` → execution layer
* `aegis_integration/` → scope adapters
* `benchmark/` → tasks + target repos
* `runners/` → execution scripts
* `results/` → run artifacts

---

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional:

```bash
cp .env.example .env
# set AEGIS_API_KEY and AEGIS_BASE_URL
```

---

## Run

```bash
# stable
python main.py baseline
python main.py aegis
python main.py compare

# stress
python main.py stress_baseline
python main.py stress_aegis
python main.py compare_stress

# full
python main.py all
python main.py all_stress
```

---

## Outputs

Each run creates:

* `summary.json`
* `task_results.json`
* `metrics.json`

Per-task:

* `aegis_result_rag.json`
* `aegis_result_context.json`
* `aegis_result_llm.json`
* `aegis_result_step.json` (if activated)
* `aegis_result_agent.json`
* `scope_usage.json`

Stress mode adds:

* `coordination_log.json`
* `agent_decisions.json`

---

## Where Aegis sits

Aegis is inserted at boundaries:

* retrieval → `rag`
* context state → `context`
* planning → `llm`
* retry/coordination → `step`
* task lifecycle → `agent`

It does not replace:

* your agent
* your model
* your tools
* your framework

---

## What this proves

* Runtime control improves real system behavior
* Improvements come from coordination, not intelligence
* The same pipeline becomes more efficient and stable

---

## Limitations

* Requires live backend for full behavior
* Fallback logic is simplified
* Planner is intentionally lightweight

---

## Summary

Aegis does not build your system.

It makes your system behave.
