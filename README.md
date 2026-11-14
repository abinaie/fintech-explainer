# Project 0 — Fintech Explainer LLM App

Your first shipped AI-engineer project. A small FastAPI app that answers
payment questions in plain English, with a source, a token counter, and a
cost-per-query readout.

**What it proves:** you can ship an LLM API app end-to-end — API, structured
output, evals, Docker — not just a notebook.

## Setup (10 minutes)

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
# edit .env and put your own Anthropic API key in it — never commit .env
```

Set a $25/month spend limit in your Anthropic console first:
https://console.anthropic.com/settings/limits

## Run it

```bash
uvicorn app.main:app --reload
# open http://127.0.0.1:8000/docs
```

Try it:
```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is network tokenization and why is it safer than giving a merchant my card number?"}'
```

Response includes: `answer`, `source`, `model`, `input_tokens`,
`output_tokens`, `latency_ms`, `cost_usd`.

## Run with Docker

```bash
docker build -t fintech-explainer .
docker run --rm -p 8000:8000 --env-file .env fintech-explainer
```

Open `http://127.0.0.1:8000/docs` to try the API.

## Deploy on Render

Create a Web Service from this repository and select the Docker runtime.
Set `ANTHROPIC_API_KEY` in the service's environment settings.
Optionally set `LLM_MODEL`; the container listens on Render's `PORT`.
Use `/health` as the health check path.
Never add `.env` or an API key to the repository.

## Evals

```bash
python -m app.eval
```

Runs the 20-question test set in `app/eval.py` and prints:
each answer, key facts to check, median latency, and total cost.
Score correct / wrong / hallucinated by hand — that's the point. Then automate.

## Files

- `app/main.py` — FastAPI app, LLM call, structured output, cost calculator
- `app/eval.py` — 20-question eval set + runner
- `app/pricing.py` — per-model pricing table (Nov 2026, update if rates change)
- `requirements.txt` — Python deps
- `Dockerfile` — `docker build -t fintech-explainer .` then run it
- `.env.example` — copy to `.env`, fill in your key

## Cost control

- Default model is the cheap one: `claude-haiku-5-5` ($0.10 input / $0.50 output
  per 1M tokens, Nov 2026). Set `LLM_MODEL=claude-sonnet-5-5` in `.env` only
  when you want a quality check.
- Every `/ask` response shows its own cost, so you can see it add up.
- If you run all 20 eval questions on Haiku, expect well under $0.10 total.

## Next step after this works

Project 1 is RAG over public payments docs — same app shape, plus
retrieval, citations to document chunks, and Ragas / DeepEval evals.
