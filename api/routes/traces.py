import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import Trace

router = APIRouter(prefix="/v1/traces", tags=["traces"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TraceIn(BaseModel):
    trace_id: str
    timestamp: str
    function_name: str
    module: str
    model: str
    input_preview: str = ""
    output_preview: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: int
    cost_usd: Optional[float] = None
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    tags: Dict[str, Any] = {}


class TraceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trace_id: str
    timestamp: datetime
    function_name: str
    module: str
    model: str
    input_preview: Optional[str]
    output_preview: Optional[str]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    latency_ms: Optional[int]
    cost_usd: Optional[float]
    error_class: Optional[str]
    error_message: Optional[str]
    tags: Optional[str]


class TracesResponse(BaseModel):
    total: int
    traces: List[TraceOut]
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/", status_code=201)
async def ingest_traces(
    payload: List[TraceIn],
    db: AsyncSession = Depends(get_db),
):
    rows = []
    for item in payload:
        try:
            ts = datetime.fromisoformat(item.timestamp.replace("Z", "+00:00"))
        except ValueError:
            ts = datetime.now(timezone.utc)

        row = Trace(
            trace_id=item.trace_id,
            timestamp=ts,
            function_name=item.function_name,
            module=item.module,
            model=item.model,
            input_preview=item.input_preview[:2000] if item.input_preview else None,
            output_preview=item.output_preview[:2000] if item.output_preview else None,
            prompt_tokens=item.prompt_tokens,
            completion_tokens=item.completion_tokens,
            total_tokens=item.total_tokens,
            latency_ms=item.latency_ms,
            cost_usd=item.cost_usd,
            error_class=item.error_class,
            error_message=item.error_message,
            tags=json.dumps(item.tags),
        )
        rows.append(row)

    db.add_all(rows)
    await db.commit()
    return {"inserted": len(rows)}


@router.get("/", response_model=TracesResponse)
async def list_traces(
    model: Optional[str] = None,
    tag: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    has_error: Optional[bool] = None,
    limit: int = Query(default=50, le=200, ge=1),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    base_q = select(Trace)

    if model:
        base_q = base_q.where(Trace.model == model)
    if tag:
        key, sep, value = tag.partition(":")
        if sep and value:
            # JSON string contains both key and value — simple substring match
            base_q = base_q.where(Trace.tags.contains(f'"{key}"'))
            base_q = base_q.where(Trace.tags.contains(f'"{value}"'))
        else:
            base_q = base_q.where(Trace.tags.contains(f'"{key}"'))
    if start_date:
        base_q = base_q.where(Trace.timestamp >= start_date)
    if end_date:
        base_q = base_q.where(Trace.timestamp <= end_date)
    if has_error is True:
        base_q = base_q.where(Trace.error_class.isnot(None))
    elif has_error is False:
        base_q = base_q.where(Trace.error_class.is_(None))

    count_q = select(func.count()).select_from(base_q.subquery())
    total = await db.scalar(count_q) or 0

    data_q = base_q.order_by(Trace.timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(data_q)
    traces = result.scalars().all()

    return TracesResponse(total=total, traces=list(traces), limit=limit, offset=offset)


@router.get("/{trace_id}", response_model=TraceOut)
async def get_trace(trace_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Trace).where(Trace.trace_id == trace_id))
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return row
