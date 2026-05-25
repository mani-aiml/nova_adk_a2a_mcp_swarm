# Swarm Agent Evaluation (Parts 2-3)

This directory contains the full evaluation suite for the art appraisal swarm.
It covers four evaluation layers: unit, integration, trace, and adversarial.

## Four lifecycle surfaces

| Surface | Role | Typical commands |
|--------|------|------------------|
| **01. ADK Web** | Author goldens, run **Run Evaluation**, inspect session graph / verification | `adk web` (see [ADK Evaluate](https://google.github.io/adk-docs/evaluate/)) |
| **02. Host CLI** | Local regression; host must reach MCP / agents if you run `adk eval` | `./evaluation/run_evals.sh`, `pytest evaluation/...` |
| **03. CI** | Gate merges without Docker; pytest unit + integration; JUnit artifact | `.github/workflows/evaluation.yml` |
| **04. Eval runner (Docker)** | `adk eval` + pytest **on** `appraisal-net` (MCP + A2A URLs set automatically) | `docker compose --profile eval run --rm eval-runner` (see root `README.md`) |

ADK Web is for **agent execution** visibility; for **distributed OTLP** traces across containers use **Jaeger** (or Grafana Tempo) — see root `docker-compose.yml` and `otel_setup.py`.

**Scaling (10+ agents):** See the **Evaluation pyramid** and **shard/matrix** guidance in the root [README.md](../README.md#evaluation-and-scaling).

## Evaluation layers

| Layer | What it tests | When to run |
|-------|----------------|-------------|
| Unit | Per-specialist goldens + synthesis (registry-driven) | Every commit |
| Integration | Swarm trajectory + scale-from-registry | Before release / with Docker |
| Trace | OTEL JSONL from a live run | After compose + workload; needs `--log-path` |
| Adversarial | Red teaming per defense point; Attack Success Rate gate | Every commit (CI) |

## Quick start

```bash
pip install -r requirements.txt adk pytest pyyaml

# Pytest only (matches CI scope; no Docker)
pytest evaluation/unit evaluation/integration -v

# Adversarial suite (Part 3): red teaming per defense point, no Docker
pytest evaluation/adversarial -v
python evaluation/adversarial/asr_runner.py

# Full suite: ADK eval per eval_package, pytest, integration, swarm eval, trace (if otel.log exists)
./evaluation/run_evals.sh

# Unit slice (pytest unit only; still runs adk eval loop unless you use pytest alone)
./evaluation/run_evals.sh --unit-only

# CI-friendly ADK config (no judge-heavy criteria)
ADK_EVAL_CONFIG=evaluation/test_config.ci.json ./evaluation/run_evals.sh

# Trace tests (log must exist; per-service OTEL resource names or tests skip)
pytest evaluation/trace_eval/test_trace_quality.py -v --log-path ./otel.log

# Generate the HTML report manually (run_evals.sh does this automatically)
python evaluation/generate_report.py --results-dir eval_results
# Report at: eval_results/eval_report.html
```

**Docker / trace file:** The orchestrator mounts **`./otel_logs` → `/otel_logs`** and sets **`OTEL_LOG_PATH=/otel_logs/otel.log`**, so Docker never creates a mistaken host **directory** named `otel.log` (which would break a single-file bind mount when the file was missing). Host output: **`otel_logs/otel.log`**. Local CLI runs can still write **`otel.log`** at the repo root when not using that path.

## Directory structure

```
evaluation/
  lib/
    trajectory.py              Shared IN_ORDER trajectory scoring
    registry_maps.py           Swarm tool order + trace service name helpers
    intermediate_semantic.py   Notes on intermediate NL vs OTEL backends
  unit/
    test_specialists_golden.py Parametrized unit evals from agents.yaml + golden/*/evalset.json
    test_synthesis_agent.py
    test_intermediate_goldens.py
    test_vote_vocabulary.py       Canonical vote labels + normalization
  integration/
    test_swarm_trajectory.py   End-to-end trajectory + registry alignment
    test_swarm_at_scale.py
  trace_eval/
    trace_analyzer.py
    test_trace_quality.py
  adversarial/                  Part 3 red teaming suite, one module per defense point
    attacks/corpus.json         Attack corpus (data; replace with attacks for your system)
    asr_runner.py               Attack Success Rate runner + CI gate
    test_dp1..dp5, test_asr.py  One module per defense point + the ASR gate
  golden/
    <eval_package>/evalset.json   One dir per eval_package from agents.yaml
    swarm/trajectory_evalset.json Curated full-swarm trajectory (exception to “data only”)
  conftest.py
  test_config.json              Default thresholds + criteria (incl. hallucinations_v1 intermediates)
  test_config.ci.json           Lighter criteria for constrained environments
  rubrics_tool_use.json         Optional human-editable rubric text
  list_eval_packages.py         Prints eval_package lines for run_evals.sh
  generate_report.py            Builds eval_report.html from JUnit XML + ADK eval JSON
  run_evals.sh                  Strict ADK eval (failures are not masked)
  docker/run_network_eval.sh    Sets Compose-network URLs; entrypoint for eval-runner image
```

Eval-runner image is built from [eval_runner/Dockerfile](../eval_runner/Dockerfile).

## Adding a new specialist (scale by convention)

1. Add the specialist to **`agents.yaml`**: `name`, `service_name`, `tools`, `description`, and **`eval_package`** (Python package path used by `adk eval`, e.g. `style_agent`). Goldens live under `evaluation/golden/<eval_package>/`.
2. Add **`evaluation/golden/<eval_package>/evalset.json`** with ADK-native invocations: **`user_content`**, **`final_response`** (golden final text), **`intermediate_data.tool_uses`** (expected tools as `{ "name", "args" }`), and optional **`intermediate_data.intermediate_responses`** as `[author, parts]` pairs for intermediate grounding. Thresholds live in `test_config.json` (`hallucinations_v1` with `evaluate_intermediate_nl_responses`, optional `rubric_based_tool_use_quality_v1`). Helpers: `evaluation/lib/golden_io.py`.
3. **No new per-agent pytest file** — `test_specialists_golden.py` discovers specialists from the registry.

**Exceptions:** The **full swarm** golden `golden/swarm/trajectory_evalset.json` stays hand-maintained for combined parallel tool order. `test_swarm_trajectory.py` uses registry-derived specialist tool lists (`specialist_tools`, `full_swarm_expected_tool_order`).

## Evaluation criteria (`test_config.json`)

| Metric | Notes |
|--------|--------|
| `tool_trajectory_avg_score` | IN_ORDER tool trajectory vs golden |
| `response_match_score` / `final_response_match_v2` | Lexical / LLM judge on final answer |
| `hallucinations_v1` | Grounding; enable `evaluate_intermediate_nl_responses` for intermediate steps |
| `rubric_based_tool_use_quality_v1` | Optional rubric judge (see `rubrics_tool_use.json`) |

## CI

The **Evaluation CI** workflow (`.github/workflows/evaluation.yml`) runs four jobs on every push / PR to `main`:

| Job | What it runs | Artifact |
|-----|-------------|----------|
| **Unit Tests** | `pytest evaluation/unit/` | `unit_tests.xml` (JUnit) |
| **Integration Tests** | `pytest evaluation/integration/` | `integration_tests.xml` (JUnit) |
| **Adversarial Tests** | `pytest evaluation/adversarial/` + `asr_runner.py` (ASR gate) | `adversarial_tests.xml`, `adversarial_asr.json` |
| **Report** | `generate_report.py` (merges all JUnit XMLs) | `eval_report.html` |

CI does **not** run Docker, `adk eval`, or trace tests. For release gates that include ADK eval and Docker integration, run `./evaluation/run_evals.sh` locally or use the Docker eval runner.

## Trace analysis

After a live swarm run, traces may be in **`otel.log`** (file exporter) and/or exported via **OTLP** to Jaeger (`docker compose` Jaeger service).

```bash
python evaluation/trace_eval/trace_analyzer.py --log otel.log
python evaluation/trace_eval/trace_analyzer.py --log otel.log --agent style-agent --json
```

Trace pytest tests expect **per-container `service.name`** (e.g. `style-agent`) in the log. Monolithic logs with a single service name cause **skipped** completeness tests with an explanatory message.
