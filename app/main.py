"""Project 0 — Fintech Explainer LLM App.

FastAPI app: POST /ask with a payment question, get a short plain-English
answer with a source, plus tokens, latency, and cost per query.

Uses the Anthropic Claude API (not ChatGPT / OpenAI).

Setup: cp .env.example .env, put your own ANTHROPIC_API_KEY in .env,
set a $25/month spend limit in the Anthropic console
(console.anthropic.com > Settings > Limits), then:
    uvicorn app.main:app --reload
"""

import json
import os
import time

from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.pricing import cost_usd

load_dotenv()

MODEL = os.getenv("LLM_MODEL", "claude-haiku-5-5")
API_KEY = os.getenv("ANTHROPIC_API_KEY")

SYSTEM_PROMPT = (
    "You are a fintech explainer. Answer payment questions in short, "
    "plain English for a smart non-expert. Keep answers to 3-5 sentences. "
    "If you are unsure, say so plainly instead of guessing. "
    "Always name one source type the reader could check "
    "(e.g. card network documentation, PCI DSS, a bank's help page) — "
    "do not invent a specific URL. "
    "Reply with ONLY a JSON object: {\"answer\": \"...\", \"source\": \"...\"}. "
    "No other text, no markdown fences."
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)


class AskResponse(BaseModel):
    answer: str
    source: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float


app = FastAPI(title="Fintech Explainer")


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.",
        )
    client = Anthropic(api_key=API_KEY)
    start = time.time()
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=400,
            temperature=0.2,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": req.question}],
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM call failed: {e}")

    text = "".join(
        block.text for block in resp.content if getattr(block, "type", "") == "text"
    ).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fallback: model returned plain text instead of JSON.
        data = {"answer": text, "source": "not provided"}

    usage = resp.usage
    latency_ms = int((time.time() - start) * 1000)
    return AskResponse(
        answer=data["answer"],
        source=data["source"],
        model=MODEL,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        latency_ms=latency_ms,
        cost_usd=round(
            cost_usd(MODEL, usage.input_tokens, usage.output_tokens), 6
        ),
    )
