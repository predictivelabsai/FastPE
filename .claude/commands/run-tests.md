# Run Tests

Run the PEHero test suite (smoke tests, regression, evals).

## Smoke tests (no LLM, fast)

```bash
pytest -q tests/test_agents_smoke.py
```

41 tests: builds every agent, checks routing, validates tool shapes. No API keys needed.

## Single test

```bash
pytest -q tests/test_agents_smoke.py::test_lbo_round_trip
```

## Full regression (hits LLM)

```bash
# All 25 agents
python -m tests.regression_suite

# Single agent
python -m tests.regression_suite --slug deal_triage
```

Writes results to `docs/regression-latest.md`.

## Evals

```bash
python -m evals.run_routing_eval     # routing accuracy
python -m evals.run_response_eval    # response quality scoring
python -m evals.run_game_eval        # PE Hero game eval
```

## Pre-commit checks

Always run before committing:

```bash
# 1. Dependency check (no missing imports)
.venv/bin/python -c "..." # (see CLAUDE.md for full script)

# 2. Smoke tests
pytest -q tests/test_agents_smoke.py

# 3. Boot check
.venv/bin/python -c "from app import app; from chat import routes, pipeline, instructions, analytics, companies, memo_pdf, exports, dataroom, help, valuation, webhooks, integrations, training, investors, portfolio; from auth import routes as _auth; print('app imports OK')"
```
