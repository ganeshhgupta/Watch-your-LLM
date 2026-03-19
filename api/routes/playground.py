"""
/v1/playground/* — Interactive LLM playground, all calls auto-traced to DB.

POST /v1/playground/chat    — multi-turn chat with context
POST /v1/playground/cot     — chain-of-thought reasoning (3 LLM steps)
POST /v1/playground/rag     — RAG over a user-supplied document
POST /v1/playground/agent   — agentic workflows (research / code / debate)
"""

import json
import math
import os
import re
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Trace

router = APIRouter(prefix="/v1/playground", tags=["playground"])

MODEL = "llama-3.1-8b-instant"
PRICING = {"input": 0.05, "output": 0.08}  # USD per 1M tokens


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cost(p: int, c: int) -> float:
    return (p * PRICING["input"] + c * PRICING["output"]) / 1_000_000


async def _call(
    client,
    messages: List[Dict],
    fn: str,
    session_id: str,
    db: AsyncSession,
    extra_tags: Dict = {},
) -> str:
    """One Groq call → save trace → return assistant text."""
    trace_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc)
    t0 = time.perf_counter()
    output = error_class = error_msg = None
    pt = ct = total = None
    cost = None
    input_preview = messages[-1]["content"][:2000]

    try:
        resp = await client.chat.completions.create(model=MODEL, messages=messages)
        output = resp.choices[0].message.content
        pt = resp.usage.prompt_tokens
        ct = resp.usage.completion_tokens
        total = resp.usage.total_tokens
        cost = _cost(pt, ct)
    except Exception as exc:
        error_class = type(exc).__name__
        error_msg = str(exc)[:500]

    latency = int((time.perf_counter() - t0) * 1000)

    db.add(Trace(
        trace_id=trace_id, timestamp=ts,
        function_name=fn, module="playground", model=MODEL,
        input_preview=input_preview,
        output_preview=(output or "")[:2000],
        prompt_tokens=pt, completion_tokens=ct, total_tokens=total,
        latency_ms=latency, cost_usd=cost,
        error_class=error_class, error_message=error_msg,
        tags=json.dumps({"session": session_id, "source": "playground", **extra_tags}),
    ))
    await db.commit()

    if error_class:
        raise HTTPException(500, error_msg)
    return output


def _groq_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(500, "GROQ_API_KEY not configured on server")
    from groq import AsyncGroq
    return AsyncGroq(api_key=api_key)


# ---------------------------------------------------------------------------
# RAG helpers — keyword retrieval, no vector DB needed
# ---------------------------------------------------------------------------

def _chunk(text: str, size: int = 250) -> List[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i: i + size]))
        i += size - 40
    return [c for c in chunks if len(c.strip()) > 30]


def _bm25_score(query: str, chunk: str) -> float:
    q_terms = re.findall(r"\w+", query.lower())
    c_terms = re.findall(r"\w+", chunk.lower())
    freq = Counter(c_terms)
    k, b, avg = 1.5, 0.75, 250
    score = 0.0
    for t in q_terms:
        tf = freq[t]
        score += math.log(2) * (tf * (k + 1)) / (tf + k * (1 - b + b * len(c_terms) / avg))
    return score


def _retrieve(query: str, text: str, k: int = 3) -> List[str]:
    chunks = _chunk(text)
    return sorted(chunks, key=lambda c: _bm25_score(query, c), reverse=True)[:k]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    session_id: str = "default"

class CotRequest(BaseModel):
    question: str
    session_id: str = "default"

class RagRequest(BaseModel):
    document: str
    question: str
    session_id: str = "default"

class AgentRequest(BaseModel):
    agent_type: str   # "research" | "code" | "debate"
    task: str
    session_id: str = "default"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/chat")
async def playground_chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    client = _groq_client()
    messages = [{"role": "system", "content": "You are a helpful, concise AI assistant."}] + req.messages
    reply = await _call(client, messages, "chat", req.session_id, db, {"type": "chat"})
    return {"reply": reply}


@router.post("/cot")
async def playground_cot(req: CotRequest, db: AsyncSession = Depends(get_db)):
    client = _groq_client()
    tags = {"type": "cot"}

    plan = await _call(client, [
        {"role": "system", "content": "You are an analytical reasoner. Break problems into clear numbered steps."},
        {"role": "user", "content": f"Break this into 3-4 reasoning steps:\n\n{req.question}"},
    ], "cot_plan", req.session_id, db, {**tags, "step": "plan"})

    reasoning = await _call(client, [
        {"role": "system", "content": "You are a methodical reasoner. Work through each step carefully."},
        {"role": "user", "content": f"Question: {req.question}\n\nSteps:\n{plan}\n\nWork through each step in detail:"},
    ], "cot_reason", req.session_id, db, {**tags, "step": "reason"})

    answer = await _call(client, [
        {"role": "system", "content": "You are precise and concise. Summarise into a clean final answer."},
        {"role": "user", "content": f"Question: {req.question}\n\nReasoning:\n{reasoning}\n\nFinal answer:"},
    ], "cot_answer", req.session_id, db, {**tags, "step": "answer"})

    return {"plan": plan, "reasoning": reasoning, "answer": answer}


@router.post("/rag")
async def playground_rag(req: RagRequest, db: AsyncSession = Depends(get_db)):
    client = _groq_client()
    chunks = _retrieve(req.question, req.document)
    context = "\n\n---\n\n".join(chunks)
    answer = await _call(client, [
        {"role": "system", "content": "Answer using ONLY the provided context. If the answer isn't there, say so."},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {req.question}"},
    ], "rag_generate", req.session_id, db, {"type": "rag"})
    return {"chunks": chunks, "answer": answer}


@router.post("/agent")
async def playground_agent(req: AgentRequest, db: AsyncSession = Depends(get_db)):
    client = _groq_client()
    if req.agent_type == "research":
        return await _research_agent(client, req.task, req.session_id, db)
    elif req.agent_type == "code":
        return await _code_agent(client, req.task, req.session_id, db)
    elif req.agent_type == "debate":
        return await _debate_agent(client, req.task, req.session_id, db)
    raise HTTPException(400, f"Unknown agent_type: {req.agent_type}")


async def _research_agent(client, task, session_id, db):
    t = {"type": "agent", "agent": "research"}
    plan = await _call(client, [
        {"role": "system", "content": "You are a research planner. Create a concise 3-step research plan."},
        {"role": "user", "content": f"Create a research plan for: {task}"},
    ], "agent_plan", session_id, db, {**t, "step": "plan"})

    findings = await _call(client, [
        {"role": "system", "content": "You are a research analyst. Provide detailed, factual findings."},
        {"role": "user", "content": f"Research plan:\n{plan}\n\nProvide findings for each step on: {task}"},
    ], "agent_research", session_id, db, {**t, "step": "research"})

    report = await _call(client, [
        {"role": "system", "content": "You are a report writer. Write a clear executive summary."},
        {"role": "user", "content": f"Findings:\n{findings}\n\nWrite an executive summary on: {task}"},
    ], "agent_synthesize", session_id, db, {**t, "step": "synthesize"})

    return {"steps": [
        {"title": "Research Plan", "content": plan},
        {"title": "Findings", "content": findings},
        {"title": "Executive Summary", "content": report},
    ]}


async def _code_agent(client, task, session_id, db):
    t = {"type": "agent", "agent": "code"}
    design = await _call(client, [
        {"role": "system", "content": "You are a software architect. Analyse the task and outline your approach."},
        {"role": "user", "content": f"Analyse and outline an approach for:\n{task}"},
    ], "agent_design", session_id, db, {**t, "step": "design"})

    code = await _call(client, [
        {"role": "system", "content": "You are an expert programmer. Write clean, well-commented code."},
        {"role": "user", "content": f"Task: {task}\n\nApproach:\n{design}\n\nWrite the implementation:"},
    ], "agent_code", session_id, db, {**t, "step": "code"})

    review = await _call(client, [
        {"role": "system", "content": "You are a code reviewer. Explain the code and suggest improvements."},
        {"role": "user", "content": f"Review and explain:\n{code}"},
    ], "agent_review", session_id, db, {**t, "step": "review"})

    return {"steps": [
        {"title": "Design & Approach", "content": design},
        {"title": "Implementation", "content": code},
        {"title": "Review & Explanation", "content": review},
    ]}


async def _debate_agent(client, task, session_id, db):
    t = {"type": "agent", "agent": "debate"}
    pro = await _call(client, [
        {"role": "system", "content": "You are a skilled debater. Argue persuasively IN FAVOR with evidence."},
        {"role": "user", "content": f"Argue strongly FOR: {task}"},
    ], "agent_pro", session_id, db, {**t, "step": "pro"})

    con = await _call(client, [
        {"role": "system", "content": "You are a skilled debater. Challenge the pro argument and argue AGAINST."},
        {"role": "user", "content": f"Topic: {task}\n\nPro argues:\n{pro}\n\nNow argue strongly AGAINST:"},
    ], "agent_con", session_id, db, {**t, "step": "con"})

    verdict = await _call(client, [
        {"role": "system", "content": "You are an impartial moderator. Summarise both sides and give a balanced verdict."},
        {"role": "user", "content": f"Topic: {task}\n\nPro:\n{pro}\n\nCon:\n{con}\n\nYour balanced verdict:"},
    ], "agent_verdict", session_id, db, {**t, "step": "verdict"})

    return {"steps": [
        {"title": "Pro Argument", "content": pro},
        {"title": "Counter Argument", "content": con},
        {"title": "Moderator Verdict", "content": verdict},
    ]}


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def _sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


def _think(text: str) -> str:
    return _sse({"type": "thinking", "text": text})


def _step(title: str, content: str) -> str:
    return _sse({"type": "step", "title": title, "content": content})


# ---------------------------------------------------------------------------
# Streaming endpoints  (POST → text/event-stream)
# ---------------------------------------------------------------------------

@router.post("/cot/stream")
async def playground_cot_stream(req: CotRequest, db: AsyncSession = Depends(get_db)):
    client = _groq_client()
    tags = {"type": "cot"}

    async def generate() -> AsyncGenerator[str, None]:
        yield _think("Reading the question and identifying key components...")
        plan = await _call(client, [
            {"role": "system", "content": "You are an analytical reasoner. Break problems into clear numbered steps."},
            {"role": "user", "content": f"Break this into 3-4 reasoning steps:\n\n{req.question}"},
        ], "cot_plan", req.session_id, db, {**tags, "step": "plan"})
        yield _step("1 · Break it down", plan)

        yield _think("Working through each step methodically...")
        reasoning = await _call(client, [
            {"role": "system", "content": "You are a methodical reasoner. Work through each step carefully."},
            {"role": "user", "content": f"Question: {req.question}\n\nSteps:\n{plan}\n\nWork through each step in detail:"},
        ], "cot_reason", req.session_id, db, {**tags, "step": "reason"})
        yield _step("2 · Reason through it", reasoning)

        yield _think("Synthesising a clear final answer...")
        answer = await _call(client, [
            {"role": "system", "content": "You are precise and concise. Summarise into a clean final answer."},
            {"role": "user", "content": f"Question: {req.question}\n\nReasoning:\n{reasoning}\n\nFinal answer:"},
        ], "cot_answer", req.session_id, db, {**tags, "step": "answer"})
        yield _step("3 · Final Answer", answer)

        yield _sse({"type": "done"})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/agent/stream")
async def playground_agent_stream(req: AgentRequest, db: AsyncSession = Depends(get_db)):
    client = _groq_client()

    async def research() -> AsyncGenerator[str, None]:
        t = {"type": "agent", "agent": "research"}
        yield _think("Designing a research plan...")
        plan = await _call(client, [
            {"role": "system", "content": "You are a research planner. Create a concise 3-step research plan."},
            {"role": "user", "content": f"Create a research plan for: {req.task}"},
        ], "agent_plan", req.session_id, db, {**t, "step": "plan"})
        yield _step("Research Plan", plan)

        yield _think("Gathering findings for each research step...")
        findings = await _call(client, [
            {"role": "system", "content": "You are a research analyst. Provide detailed, factual findings."},
            {"role": "user", "content": f"Research plan:\n{plan}\n\nProvide findings for each step on: {req.task}"},
        ], "agent_research", req.session_id, db, {**t, "step": "research"})
        yield _step("Findings", findings)

        yield _think("Writing executive summary...")
        report = await _call(client, [
            {"role": "system", "content": "You are a report writer. Write a clear executive summary."},
            {"role": "user", "content": f"Findings:\n{findings}\n\nWrite an executive summary on: {req.task}"},
        ], "agent_synthesize", req.session_id, db, {**t, "step": "synthesize"})
        yield _step("Executive Summary", report)
        yield _sse({"type": "done"})

    async def code() -> AsyncGenerator[str, None]:
        t = {"type": "agent", "agent": "code"}
        yield _think("Analysing the task and designing an approach...")
        design = await _call(client, [
            {"role": "system", "content": "You are a software architect. Analyse the task and outline your approach."},
            {"role": "user", "content": f"Analyse and outline an approach for:\n{req.task}"},
        ], "agent_design", req.session_id, db, {**t, "step": "design"})
        yield _step("Design & Approach", design)

        yield _think("Writing the implementation...")
        impl = await _call(client, [
            {"role": "system", "content": "You are an expert programmer. Write clean, well-commented code."},
            {"role": "user", "content": f"Task: {req.task}\n\nApproach:\n{design}\n\nWrite the implementation:"},
        ], "agent_code", req.session_id, db, {**t, "step": "code"})
        yield _step("Implementation", impl)

        yield _think("Reviewing and explaining the code...")
        review = await _call(client, [
            {"role": "system", "content": "You are a code reviewer. Explain the code and suggest improvements."},
            {"role": "user", "content": f"Review and explain:\n{impl}"},
        ], "agent_review", req.session_id, db, {**t, "step": "review"})
        yield _step("Review & Explanation", review)
        yield _sse({"type": "done"})

    async def debate() -> AsyncGenerator[str, None]:
        t = {"type": "agent", "agent": "debate"}
        yield _think("Constructing the pro argument...")
        pro = await _call(client, [
            {"role": "system", "content": "You are a skilled debater. Argue persuasively IN FAVOR with evidence."},
            {"role": "user", "content": f"Argue strongly FOR: {req.task}"},
        ], "agent_pro", req.session_id, db, {**t, "step": "pro"})
        yield _step("Pro Argument", pro)

        yield _think("Formulating the counter argument...")
        con = await _call(client, [
            {"role": "system", "content": "You are a skilled debater. Challenge the pro argument and argue AGAINST."},
            {"role": "user", "content": f"Topic: {req.task}\n\nPro argues:\n{pro}\n\nNow argue strongly AGAINST:"},
        ], "agent_con", req.session_id, db, {**t, "step": "con"})
        yield _step("Counter Argument", con)

        yield _think("Moderator is weighing both sides...")
        verdict = await _call(client, [
            {"role": "system", "content": "You are an impartial moderator. Summarise both sides and give a balanced verdict."},
            {"role": "user", "content": f"Topic: {req.task}\n\nPro:\n{pro}\n\nCon:\n{con}\n\nYour balanced verdict:"},
        ], "agent_verdict", req.session_id, db, {**t, "step": "verdict"})
        yield _step("Moderator Verdict", verdict)
        yield _sse({"type": "done"})

    generators = {"research": research, "code": code, "debate": debate}
    if req.agent_type not in generators:
        raise HTTPException(400, f"Unknown agent_type: {req.agent_type}")

    return StreamingResponse(generators[req.agent_type](), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
