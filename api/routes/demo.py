"""
POST /v1/demo — runs a batch of real Groq LLM calls and ingests the traces.
Anyone can hit this from the dashboard to populate the DB with live data.
"""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Trace

router = APIRouter(prefix="/v1/demo", tags=["demo"])

GROQ_MODEL = "llama-3.1-8b-instant"
PRICING = {"input": 0.05, "output": 0.08}  # USD per 1M tokens

DEMO_CALLS = [
    ("summarize",     "Summarize in 2 sentences: Machine learning enables systems to learn from data without being explicitly programmed."),
    ("classify",      "Classify sentiment (one word — positive/negative/neutral): 'I absolutely love this product, it works perfectly!'"),
    ("qa",            "Answer concisely: What is observability in software engineering?"),
    ("rewrite",       "Rewrite formally: 'hey can u fix the bug asap its super urgent lol'"),
    ("chat",          "What is the difference between precision and recall in machine learning?"),
    ("summarize",     "Summarize in 2 sentences: Python was created by Guido van Rossum in 1991 and emphasises code readability."),
    ("classify",      "Classify sentiment (one word): 'This is the worst experience I have ever had. Completely broken.'"),
    ("qa",            "Answer concisely: What are the SOLID principles in software engineering?"),
]


def _calc_cost(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens * PRICING["input"] + completion_tokens * PRICING["output"]) / 1_000_000


async def _run_demo(db: AsyncSession) -> dict:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return {"error": "GROQ_API_KEY not configured on server"}

    try:
        from groq import AsyncGroq
    except ImportError:
        return {"error": "groq package not installed on server"}

    client = AsyncGroq(api_key=api_key)
    rows = []

    for fn_name, prompt in DEMO_CALLS:
        trace_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        start = time.perf_counter()
        error_class = error_message = output_preview = None
        prompt_tokens = completion_tokens = total_tokens = None
        cost_usd = None

        try:
            resp = await client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            output_preview = resp.choices[0].message.content[:2000]
            prompt_tokens = resp.usage.prompt_tokens
            completion_tokens = resp.usage.completion_tokens
            total_tokens = resp.usage.total_tokens
            cost_usd = _calc_cost(prompt_tokens, completion_tokens)
        except Exception as exc:
            error_class = type(exc).__name__
            error_message = str(exc)[:500]

        latency_ms = int((time.perf_counter() - start) * 1000)

        rows.append(Trace(
            trace_id=trace_id,
            timestamp=timestamp,
            function_name=fn_name,
            module="demo",
            model=GROQ_MODEL,
            input_preview=prompt[:2000],
            output_preview=output_preview,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            error_class=error_class,
            error_message=error_message,
            tags=json.dumps({"env": "demo", "source": "dashboard"}),
        ))

        await asyncio.sleep(0.3)  # avoid hammering the API

    db.add_all(rows)
    await db.commit()
    return {"inserted": len(rows)}


@router.post("/")
async def run_demo(background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    """Trigger demo Groq calls in the background and ingest traces."""
    background_tasks.add_task(_run_demo, db)
    return {"status": "started", "calls": len(DEMO_CALLS), "model": GROQ_MODEL}
