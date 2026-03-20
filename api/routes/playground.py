"""
/v1/playground/* — Interactive LLM playground, all calls auto-traced to DB.
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
# RAG helpers
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
    prior_turns: List[dict] = []  # [{"question": str, "answer": str}]

class RagRequest(BaseModel):
    document: str
    question: str
    session_id: str = "default"

class AgentRequest(BaseModel):
    agent_type: str   # "research" | "code" | "debate"
    task: str
    session_id: str = "default"
    prior_context: str = ""  # summary of prior exchange for follow-ups


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/chat")
async def playground_chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    client = _groq_client()
    messages = [{"role": "system", "content": "You are a helpful, concise AI assistant."}] + req.messages
    reply = await _call(client, messages, "chat", req.session_id, db, {"type": "chat"})
    return {"reply": reply}


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
# CoT streaming — multi-turn aware, convergence extension
# ---------------------------------------------------------------------------

@router.post("/cot/stream")
async def playground_cot_stream(req: CotRequest, db: AsyncSession = Depends(get_db)):
    client = _groq_client()
    tags = {"type": "cot"}

    # Build context string from prior turns (last 3)
    prior_ctx = ""
    if req.prior_turns:
        entries = req.prior_turns[-3:]
        prior_ctx = "Prior reasoning in this session:\n" + "\n\n".join(
            f"Q: {t.get('question', '')}\nConclusion: {str(t.get('answer', ''))[:400]}"
            for t in entries
        ) + "\n\n---\nNew question to reason through:\n"

    async def generate() -> AsyncGenerator[str, None]:
        yield _think("Reading the question and identifying key components...")
        plan = await _call(client, [
            {"role": "system", "content": "You are an analytical reasoner. Break problems into clear numbered steps. Consider prior session context where relevant."},
            {"role": "user", "content": f"{prior_ctx}Break this into 3-4 reasoning steps:\n\n{req.question}"},
        ], "cot_plan", req.session_id, db, {**tags, "step": "plan"})
        yield _step("1 · Break it down", plan)

        yield _think("Working through each step methodically...")
        reasoning = await _call(client, [
            {"role": "system", "content": "You are a methodical reasoner. Work through each step carefully, building on prior session context if relevant."},
            {"role": "user", "content": f"{prior_ctx}Question: {req.question}\n\nSteps:\n{plan}\n\nWork through each step in detail:"},
        ], "cot_reason", req.session_id, db, {**tags, "step": "reason"})
        yield _step("2 · Reason through it", reasoning)

        yield _think("Synthesising a clear final answer...")
        answer = await _call(client, [
            {"role": "system", "content": "You are precise and concise. Summarise into a clean final answer."},
            {"role": "user", "content": f"Question: {req.question}\n\nReasoning:\n{reasoning}\n\nFinal answer:"},
        ], "cot_answer", req.session_id, db, {**tags, "step": "answer"})
        yield _step("3 · Final Answer", answer)

        # Convergence check — extend if answer is incomplete
        try:
            conv = await _call(client, [
                {"role": "system", "content": "Reply with exactly one word: RESOLVED or EXTEND."},
                {"role": "user", "content": f"Question: {req.question}\n\nAnswer provided:\n{answer[:800]}\n\nIs this answer complete and satisfactory?"},
            ], "convergence_check", req.session_id, db, {**tags, "step": "convergence"})
            if "EXTEND" in conv.upper():
                yield _think("🔄 Answer needs more depth — extending analysis...")
                deeper = await _call(client, [
                    {"role": "system", "content": "You are deepening a reasoning chain. Address the most critical aspect that was underexplored."},
                    {"role": "user", "content": f"Question: {req.question}\n\nInitial answer:\n{answer}\n\nWhat important aspect was missed or needs deeper treatment? Provide it now:"},
                ], "cot_extend", req.session_id, db, {**tags, "step": "extend"})
                yield _step("4 · Deeper Analysis", deeper)
        except Exception:
            pass  # convergence check is best-effort, never blocks output

        yield _sse({"type": "done"})

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------------------
# Agent streaming — multi-turn aware, convergence extension
# ---------------------------------------------------------------------------

@router.post("/agent/stream")
async def playground_agent_stream(req: AgentRequest, db: AsyncSession = Depends(get_db)):
    client = _groq_client()
    ctx_note = f"\n\n[Prior session context: {req.prior_context[:600]}]" if req.prior_context else ""

    async def research() -> AsyncGenerator[str, None]:
        t = {"type": "agent", "agent": "research"}

        yield _think("🔬 Researcher forming initial hypothesis...")
        hypothesis = await _call(client, [
            {"role": "system", "content": f"You are a rigorous researcher. Propose a detailed hypothesis and initial findings on the topic. Be specific and cite reasoning.{ctx_note}"},
            {"role": "user", "content": f"Topic: {req.task}\n\nPropose a detailed research hypothesis and initial analysis."},
        ], "researcher_hypothesis", req.session_id, db, {**t, "round": "1", "role": "researcher"})
        yield _step("🔬 Researcher — Hypothesis", hypothesis)

        yield _think("⚡ Critic identifying weaknesses and gaps...")
        critique = await _call(client, [
            {"role": "system", "content": "You are a sharp academic critic. Find flaws, gaps, and unsupported claims in the researcher's hypothesis. Be pointed and specific."},
            {"role": "user", "content": f"Topic: {req.task}\n\nResearcher's hypothesis:\n{hypothesis}\n\nIdentify the key weaknesses and gaps in this analysis."},
        ], "critic_challenge", req.session_id, db, {**t, "round": "1", "role": "critic"})
        yield _step("⚡ Critic — Challenge", critique)

        yield _think("🔬 Researcher refining based on critique...")
        refined = await _call(client, [
            {"role": "system", "content": "You are a researcher who takes criticism seriously. Address every point raised and strengthen your analysis with more evidence."},
            {"role": "user", "content": f"Topic: {req.task}\n\nYour original hypothesis:\n{hypothesis}\n\nCritic's challenges:\n{critique}\n\nRevise and strengthen your analysis addressing each critique."},
        ], "researcher_refine", req.session_id, db, {**t, "round": "2", "role": "researcher"})
        yield _step("🔬 Researcher — Refined Analysis", refined)

        yield _think("⚡ Critic evaluating the refined analysis...")
        validation = await _call(client, [
            {"role": "system", "content": "You are a critic doing a final evaluation. Acknowledge what has been addressed well, note any remaining gaps, and give your overall assessment."},
            {"role": "user", "content": f"Topic: {req.task}\n\nOriginal critique:\n{critique}\n\nResearcher's revised analysis:\n{refined}\n\nFinal evaluation — what's been addressed, what's still missing?"},
        ], "critic_validate", req.session_id, db, {**t, "round": "2", "role": "critic"})
        yield _step("⚡ Critic — Final Evaluation", validation)

        yield _think("🧠 Aggregator synthesising the full exchange into a report...")
        report = await _call(client, [
            {"role": "system", "content": "You are an objective aggregator. Synthesise the entire researcher-critic exchange into a definitive, balanced report."},
            {"role": "user", "content": f"Topic: {req.task}\n\nHypothesis:\n{hypothesis}\n\nCritique:\n{critique}\n\nRefined analysis:\n{refined}\n\nFinal evaluation:\n{validation}\n\nWrite a definitive synthesised report."},
        ], "aggregator_report", req.session_id, db, {**t, "round": "final", "role": "aggregator"})
        yield _step("🧠 Aggregator — Final Report", report)

        # Convergence extension
        try:
            conv = await _call(client, [
                {"role": "system", "content": "Reply with exactly one word: RESOLVED or EXTEND."},
                {"role": "user", "content": f"Topic: {req.task}\n\nFinal report:\n{report[:800]}\n\nIs this research comprehensive and complete?"},
            ], "convergence_check", req.session_id, db, {**t, "role": "convergence"})
            if "EXTEND" in conv.upper():
                yield _think("🔄 Critical gaps remain — extending research...")
                extra = await _call(client, [
                    {"role": "system", "content": f"You are the researcher providing crucial missing depth.{ctx_note}"},
                    {"role": "user", "content": f"Topic: {req.task}\n\nPrior findings:\n{report}\n\nDive deeper into the most critical unaddressed aspect and provide new insights:"},
                ], "researcher_extend", req.session_id, db, {**t, "round": "3", "role": "researcher"})
                yield _step("🔬 Researcher — Extended Findings", extra)
        except Exception:
            pass

        yield _sse({"type": "done"})

    async def code() -> AsyncGenerator[str, None]:
        t = {"type": "agent", "agent": "code"}

        yield _think("🏗️ Architect designing the solution...")
        design = await _call(client, [
            {"role": "system", "content": f"You are a software architect. Produce a concise design: components, data flow, key decisions, and trade-offs.{ctx_note}"},
            {"role": "user", "content": f"Design a solution for:\n{req.task}"},
        ], "architect_design", req.session_id, db, {**t, "round": "1", "role": "architect"})
        yield _step("🏗️ Architect — Design", design)

        yield _think("💻 Coder writing the implementation...")
        impl = await _call(client, [
            {"role": "system", "content": "You are an expert programmer. Write clean, working, well-commented code following the architect's design exactly."},
            {"role": "user", "content": f"Task: {req.task}\n\nArchitect's design:\n{design}\n\nWrite the full implementation:"},
        ], "coder_implement", req.session_id, db, {**t, "round": "1", "role": "coder"})
        yield _step("💻 Coder — Implementation", impl)

        yield _think("🔍 Reviewer auditing the code for bugs and issues...")
        review = await _call(client, [
            {"role": "system", "content": "You are a senior code reviewer. Find bugs, security issues, edge cases, and deviations from the design. Be specific — name line-level problems."},
            {"role": "user", "content": f"Task: {req.task}\n\nDesign:\n{design}\n\nCode to review:\n{impl}\n\nList all issues found:"},
        ], "reviewer_audit", req.session_id, db, {**t, "round": "1", "role": "reviewer"})
        yield _step("🔍 Reviewer — Issues Found", review)

        yield _think("💻 Coder fixing all reviewer issues...")
        fixed = await _call(client, [
            {"role": "system", "content": "You are the coder. Fix every issue the reviewer identified. Show the corrected code with comments explaining each fix."},
            {"role": "user", "content": f"Original code:\n{impl}\n\nReviewer issues:\n{review}\n\nProvide the fixed implementation:"},
        ], "coder_fix", req.session_id, db, {**t, "round": "2", "role": "coder"})
        yield _step("💻 Coder — Fixed Implementation", fixed)

        yield _think("🧠 Aggregator producing final certified code...")
        certified = await _call(client, [
            {"role": "system", "content": "You are a tech lead. Review the fixed code against the original requirements and produce a final summary: what was built, how to use it, and remaining considerations."},
            {"role": "user", "content": f"Task: {req.task}\n\nFinal code:\n{fixed}\n\nWrite the final delivery summary and usage guide:"},
        ], "aggregator_certify", req.session_id, db, {**t, "round": "final", "role": "aggregator"})
        yield _step("🧠 Aggregator — Delivery Summary", certified)

        # Convergence extension
        try:
            conv = await _call(client, [
                {"role": "system", "content": "Reply with exactly one word: RESOLVED or EXTEND."},
                {"role": "user", "content": f"Task: {req.task}\n\nDelivery summary:\n{certified[:800]}\n\nIs the implementation complete and production-ready?"},
            ], "convergence_check", req.session_id, db, {**t, "role": "convergence"})
            if "EXTEND" in conv.upper():
                yield _think("🔄 Implementation needs more work — extending...")
                extra = await _call(client, [
                    {"role": "system", "content": f"You are the coder addressing remaining gaps.{ctx_note}"},
                    {"role": "user", "content": f"Task: {req.task}\n\nCurrent implementation:\n{fixed}\n\nSummary gaps:\n{certified}\n\nAddress the most critical missing piece:"},
                ], "coder_extend", req.session_id, db, {**t, "round": "3", "role": "coder"})
                yield _step("💻 Coder — Additional Implementation", extra)
        except Exception:
            pass

        yield _sse({"type": "done"})

    async def debate() -> AsyncGenerator[str, None]:
        t = {"type": "agent", "agent": "debate"}

        yield _think("🔵 Agent A building opening argument...")
        a1 = await _call(client, [
            {"role": "system", "content": f"You are Agent A, arguing strongly IN FAVOR. Open with your strongest argument and three supporting points. Be direct and assertive.{ctx_note}"},
            {"role": "user", "content": f"Topic: {req.task}\n\nPresent your opening argument FOR this position."},
        ], "agent_a_open", req.session_id, db, {**t, "round": "1", "role": "agent_a"})
        yield _step("🔵 Agent A — Opening Argument", a1)

        yield _think("🔴 Agent B formulating rebuttal...")
        b1 = await _call(client, [
            {"role": "system", "content": "You are Agent B, arguing strongly AGAINST. Directly dismantle Agent A's points one by one, then present your counter-position with evidence."},
            {"role": "user", "content": f"Topic: {req.task}\n\nAgent A argued:\n{a1}\n\nDismantle their argument and present your AGAINST position:"},
        ], "agent_b_rebut", req.session_id, db, {**t, "round": "1", "role": "agent_b"})
        yield _step("🔴 Agent B — Rebuttal", b1)

        yield _think("🔵 Agent A counter-attacking Agent B's rebuttal...")
        a2 = await _call(client, [
            {"role": "system", "content": "You are Agent A. Agent B has attacked your position. Defend your original points, expose flaws in their rebuttal, and escalate with stronger evidence."},
            {"role": "user", "content": f"Topic: {req.task}\n\nYour opening:\n{a1}\n\nAgent B's rebuttal:\n{b1}\n\nCounter-attack and reinforce your position:"},
        ], "agent_a_counter", req.session_id, db, {**t, "round": "2", "role": "agent_a"})
        yield _step("🔵 Agent A — Counter-Rebuttal", a2)

        yield _think("🔴 Agent B making final closing argument...")
        b2 = await _call(client, [
            {"role": "system", "content": "You are Agent B. This is your final argument. Address Agent A's counter, expose any remaining weaknesses, and deliver a definitive closing statement."},
            {"role": "user", "content": f"Topic: {req.task}\n\nFull exchange so far:\nA: {a1}\nB: {b1}\nA: {a2}\n\nDeliver your definitive closing argument AGAINST:"},
        ], "agent_b_close", req.session_id, db, {**t, "round": "2", "role": "agent_b"})
        yield _step("🔴 Agent B — Closing Argument", b2)

        yield _think("⚖️ Moderator scoring the full debate exchange...")
        verdict = await _call(client, [
            {"role": "system", "content": "You are an impartial debate moderator and judge. Score both agents on: argument strength, evidence quality, rebuttal effectiveness, and overall persuasiveness. Declare a winner with reasoning. Format: score each criterion 1-10 for each agent."},
            {"role": "user", "content": f"Topic: {req.task}\n\nFull debate:\nA opens: {a1}\nB rebuts: {b1}\nA counters: {a2}\nB closes: {b2}\n\nScore both agents and declare the winner:"},
        ], "moderator_verdict", req.session_id, db, {**t, "round": "final", "role": "moderator"})
        yield _step("⚖️ Moderator — Scored Verdict", verdict)

        # Convergence extension — if debate is unresolved, do one more exchange
        try:
            conv = await _call(client, [
                {"role": "system", "content": "Reply with exactly one word: RESOLVED or EXTEND."},
                {"role": "user", "content": f"Topic: {req.task}\n\nModerator verdict:\n{verdict[:800]}\n\nHas this debate reached a clear, well-supported conclusion?"},
            ], "convergence_check", req.session_id, db, {**t, "role": "convergence"})
            if "EXTEND" in conv.upper():
                yield _think("🔵🔴 Debate unresolved — final exchange round...")
                a3 = await _call(client, [
                    {"role": "system", "content": "You are Agent A. The debate continues. Deliver your most compelling final point — something the moderator's feedback revealed as underexplored."},
                    {"role": "user", "content": f"Topic: {req.task}\n\nDebate so far: A={a1}, B={b1}, A={a2}, B={b2}\n\nModerator noted: {verdict[:400]}\n\nYour decisive final argument FOR:"},
                ], "agent_a_final", req.session_id, db, {**t, "round": "3", "role": "agent_a"})
                yield _step("🔵 Agent A — Final Point", a3)

                b3 = await _call(client, [
                    {"role": "system", "content": "You are Agent B. Respond to Agent A's final point with your own decisive closer."},
                    {"role": "user", "content": f"Topic: {req.task}\n\nAgent A's final point:\n{a3}\n\nYour decisive final argument AGAINST:"},
                ], "agent_b_final", req.session_id, db, {**t, "round": "3", "role": "agent_b"})
                yield _step("🔴 Agent B — Final Point", b3)
        except Exception:
            pass

        yield _sse({"type": "done"})

    generators = {"research": research, "code": code, "debate": debate}
    if req.agent_type not in generators:
        raise HTTPException(400, f"Unknown agent_type: {req.agent_type}")

    return StreamingResponse(generators[req.agent_type](), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
