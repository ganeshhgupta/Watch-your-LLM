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

        # Round 1 — Researcher proposes hypothesis
        yield _think("🔬 Researcher forming initial hypothesis...")
        hypothesis = await _call(client, [
            {"role": "system", "content": "You are a rigorous researcher. Propose a detailed hypothesis and initial findings on the topic. Be specific and cite reasoning."},
            {"role": "user", "content": f"Topic: {req.task}\n\nPropose a detailed research hypothesis and initial analysis."},
        ], "researcher_hypothesis", req.session_id, db, {**t, "round": "1", "role": "researcher"})
        yield _step("🔬 Researcher — Hypothesis", hypothesis)

        # Round 1 — Critic challenges
        yield _think("⚡ Critic identifying weaknesses and gaps...")
        critique = await _call(client, [
            {"role": "system", "content": "You are a sharp academic critic. Find flaws, gaps, and unsupported claims in the researcher's hypothesis. Be pointed and specific."},
            {"role": "user", "content": f"Topic: {req.task}\n\nResearcher's hypothesis:\n{hypothesis}\n\nIdentify the key weaknesses and gaps in this analysis."},
        ], "critic_challenge", req.session_id, db, {**t, "round": "1", "role": "critic"})
        yield _step("⚡ Critic — Challenge", critique)

        # Round 2 — Researcher refines
        yield _think("🔬 Researcher refining based on critique...")
        refined = await _call(client, [
            {"role": "system", "content": "You are a researcher who takes criticism seriously. Address every point raised and strengthen your analysis with more evidence."},
            {"role": "user", "content": f"Topic: {req.task}\n\nYour original hypothesis:\n{hypothesis}\n\nCritic's challenges:\n{critique}\n\nRevise and strengthen your analysis addressing each critique."},
        ], "researcher_refine", req.session_id, db, {**t, "round": "2", "role": "researcher"})
        yield _step("🔬 Researcher — Refined Analysis", refined)

        # Round 2 — Critic validates
        yield _think("⚡ Critic evaluating the refined analysis...")
        validation = await _call(client, [
            {"role": "system", "content": "You are a critic doing a final evaluation. Acknowledge what has been addressed well, note any remaining gaps, and give your overall assessment."},
            {"role": "user", "content": f"Topic: {req.task}\n\nOriginal critique:\n{critique}\n\nResearcher's revised analysis:\n{refined}\n\nFinal evaluation — what's been addressed, what's still missing?"},
        ], "critic_validate", req.session_id, db, {**t, "round": "2", "role": "critic"})
        yield _step("⚡ Critic — Final Evaluation", validation)

        # Aggregator synthesizes
        yield _think("🧠 Aggregator synthesising the full exchange into a report...")
        report = await _call(client, [
            {"role": "system", "content": "You are an objective aggregator. Synthesise the entire researcher-critic exchange into a definitive, balanced report."},
            {"role": "user", "content": f"Topic: {req.task}\n\nHypothesis:\n{hypothesis}\n\nCritique:\n{critique}\n\nRefined analysis:\n{refined}\n\nFinal evaluation:\n{validation}\n\nWrite a definitive synthesised report."},
        ], "aggregator_report", req.session_id, db, {**t, "round": "final", "role": "aggregator"})
        yield _step("🧠 Aggregator — Final Report", report)
        yield _sse({"type": "done"})

    async def code() -> AsyncGenerator[str, None]:
        t = {"type": "agent", "agent": "code"}

        # Architect designs
        yield _think("🏗️ Architect designing the solution...")
        design = await _call(client, [
            {"role": "system", "content": "You are a software architect. Produce a concise design: components, data flow, key decisions, and trade-offs."},
            {"role": "user", "content": f"Design a solution for:\n{req.task}"},
        ], "architect_design", req.session_id, db, {**t, "round": "1", "role": "architect"})
        yield _step("🏗️ Architect — Design", design)

        # Coder implements
        yield _think("💻 Coder writing the implementation...")
        impl = await _call(client, [
            {"role": "system", "content": "You are an expert programmer. Write clean, working, well-commented code following the architect's design exactly."},
            {"role": "user", "content": f"Task: {req.task}\n\nArchitect's design:\n{design}\n\nWrite the full implementation:"},
        ], "coder_implement", req.session_id, db, {**t, "round": "1", "role": "coder"})
        yield _step("💻 Coder — Implementation", impl)

        # Reviewer finds issues
        yield _think("🔍 Reviewer auditing the code for bugs and issues...")
        review = await _call(client, [
            {"role": "system", "content": "You are a senior code reviewer. Find bugs, security issues, edge cases, and deviations from the design. Be specific — name line-level problems."},
            {"role": "user", "content": f"Task: {req.task}\n\nDesign:\n{design}\n\nCode to review:\n{impl}\n\nList all issues found:"},
        ], "reviewer_audit", req.session_id, db, {**t, "round": "1", "role": "reviewer"})
        yield _step("🔍 Reviewer — Issues Found", review)

        # Coder fixes
        yield _think("💻 Coder fixing all reviewer issues...")
        fixed = await _call(client, [
            {"role": "system", "content": "You are the coder. Fix every issue the reviewer identified. Show the corrected code with comments explaining each fix."},
            {"role": "user", "content": f"Original code:\n{impl}\n\nReviewer issues:\n{review}\n\nProvide the fixed implementation:"},
        ], "coder_fix", req.session_id, db, {**t, "round": "2", "role": "coder"})
        yield _step("💻 Coder — Fixed Implementation", fixed)

        # Aggregator certifies
        yield _think("🧠 Aggregator producing final certified code...")
        certified = await _call(client, [
            {"role": "system", "content": "You are a tech lead. Review the fixed code against the original requirements and produce a final summary: what was built, how to use it, and remaining considerations."},
            {"role": "user", "content": f"Task: {req.task}\n\nFinal code:\n{fixed}\n\nWrite the final delivery summary and usage guide:"},
        ], "aggregator_certify", req.session_id, db, {**t, "round": "final", "role": "aggregator"})
        yield _step("🧠 Aggregator — Delivery Summary", certified)
        yield _sse({"type": "done"})

    async def debate() -> AsyncGenerator[str, None]:
        t = {"type": "agent", "agent": "debate"}

        # Round 1 — Agent A opens
        yield _think("🔵 Agent A building opening argument...")
        a1 = await _call(client, [
            {"role": "system", "content": "You are Agent A, arguing strongly IN FAVOR. Open with your strongest argument and three supporting points. Be direct and assertive."},
            {"role": "user", "content": f"Topic: {req.task}\n\nPresent your opening argument FOR this position."},
        ], "agent_a_open", req.session_id, db, {**t, "round": "1", "role": "agent_a"})
        yield _step("🔵 Agent A — Opening Argument", a1)

        # Round 1 — Agent B rebuts
        yield _think("🔴 Agent B formulating rebuttal...")
        b1 = await _call(client, [
            {"role": "system", "content": "You are Agent B, arguing strongly AGAINST. Directly dismantle Agent A's points one by one, then present your counter-position with evidence."},
            {"role": "user", "content": f"Topic: {req.task}\n\nAgent A argued:\n{a1}\n\nDismantle their argument and present your AGAINST position:"},
        ], "agent_b_rebut", req.session_id, db, {**t, "round": "1", "role": "agent_b"})
        yield _step("🔴 Agent B — Rebuttal", b1)

        # Round 2 — Agent A counter-rebuts
        yield _think("🔵 Agent A counter-attacking Agent B's rebuttal...")
        a2 = await _call(client, [
            {"role": "system", "content": "You are Agent A. Agent B has attacked your position. Defend your original points, expose flaws in their rebuttal, and escalate with stronger evidence."},
            {"role": "user", "content": f"Topic: {req.task}\n\nYour opening:\n{a1}\n\nAgent B's rebuttal:\n{b1}\n\nCounter-attack and reinforce your position:"},
        ], "agent_a_counter", req.session_id, db, {**t, "round": "2", "role": "agent_a"})
        yield _step("🔵 Agent A — Counter-Rebuttal", a2)

        # Round 2 — Agent B final argument
        yield _think("🔴 Agent B making final closing argument...")
        b2 = await _call(client, [
            {"role": "system", "content": "You are Agent B. This is your final argument. Address Agent A's counter, expose any remaining weaknesses, and deliver a definitive closing statement."},
            {"role": "user", "content": f"Topic: {req.task}\n\nFull exchange so far:\nA: {a1}\nB: {b1}\nA: {a2}\n\nDeliver your definitive closing argument AGAINST:"},
        ], "agent_b_close", req.session_id, db, {**t, "round": "2", "role": "agent_b"})
        yield _step("🔴 Agent B — Closing Argument", b2)

        # Moderator aggregates and scores
        yield _think("⚖️ Moderator scoring the full debate exchange...")
        verdict = await _call(client, [
            {"role": "system", "content": "You are an impartial debate moderator and judge. Score both agents on: argument strength, evidence quality, rebuttal effectiveness, and overall persuasiveness. Declare a winner with reasoning. Format: score each criterion 1-10 for each agent."},
            {"role": "user", "content": f"Topic: {req.task}\n\nFull debate:\nA opens: {a1}\nB rebuts: {b1}\nA counters: {a2}\nB closes: {b2}\n\nScore both agents and declare the winner:"},
        ], "moderator_verdict", req.session_id, db, {**t, "round": "final", "role": "moderator"})
        yield _step("⚖️ Moderator — Scored Verdict", verdict)
        yield _sse({"type": "done"})

    generators = {"research": research, "code": code, "debate": debate}
    if req.agent_type not in generators:
        raise HTTPException(400, f"Unknown agent_type: {req.agent_type}")

    return StreamingResponse(generators[req.agent_type](), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
