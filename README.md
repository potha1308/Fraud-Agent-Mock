# Fraud Assist Service

FastAPI service for synthetic fraud investigations.

This repository intentionally uses a flat layout so GitHub web upload cannot break Python package paths.

## Render

Build command:

```text
pip install -r requirements.txt
```

Start command:

```text
uvicorn api:app --host 0.0.0.0 --port $PORT
```

Environment:

```text
LLM_PROVIDER=offline
```

## Verify locally

```bash
pip install -r requirements.txt
python -m unittest test_agent.py -v
python evals.py
python -c "import api; print(api.health())"
```

All data is synthetic.
