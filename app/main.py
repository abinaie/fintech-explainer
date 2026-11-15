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
import math
import os
import secrets
import time
from collections import deque
from pathlib import Path
from threading import Lock
from time import monotonic

from anthropic import Anthropic
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.responses import FileResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from app.pricing import cost_usd

load_dotenv()

MODEL = os.getenv("LLM_MODEL", "claude-haiku-5-5")
API_KEY = os.getenv("ANTHROPIC_API_KEY")

SYSTEM_PROMPT = (
    "You are a fintech explainer. Answer only questions related to financial "
    "technology, including digital payments, banking, and payment security. "
    "For unrelated questions, politely say you can only help with fintech "
    "questions; do not answer the unrelated question, and set source to "
    "\"not applicable\". "
    "Answer in short, plain English for a smart non-expert. "
    "Keep fintech answers to 3-5 sentences. "
    "Avoid absolute claims when common exceptions exist; briefly qualify them "
    "or mention a relevant exception. "
    "When discussing debit-card spending limits, explain that some accounts "
    "may allow overdrafts. Never say a debit card lets you spend only what you "
    "have, even if you mention overdrafts afterward. "
    "If you are unsure, say so plainly instead of guessing. "
    "For fintech answers, name one source type the reader could check "
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
app_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
RATE_LIMIT_REQUESTS = 5
RATE_LIMIT_SECONDS = 60
recent_requests: deque[float] = deque()
rate_limit_lock = Lock()


def require_app_key(key: str | None = Security(app_key_header)) -> None:
    expected = os.getenv("APP_API_KEY")
    if not expected:
        raise HTTPException(status_code=503, detail="APP_API_KEY is not configured.")
    if not key or not secrets.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing app key.")


def enforce_rate_limit() -> None:
    with rate_limit_lock:
        now = monotonic()
        while recent_requests and recent_requests[0] <= now - RATE_LIMIT_SECONDS:
            recent_requests.popleft()
        if len(recent_requests) >= RATE_LIMIT_REQUESTS:
            retry_after = math.ceil(recent_requests[0] + RATE_LIMIT_SECONDS - now)
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )
        recent_requests.append(now)


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(Path(__file__).with_name("index.html"))


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.post(
    "/ask",
    response_model=AskResponse,
    dependencies=[Depends(require_app_key), Depends(enforce_rate_limit)],
)
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
