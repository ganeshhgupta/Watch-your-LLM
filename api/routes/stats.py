from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

router = APIRouter(prefix="/v1/stats", tags=["stats"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class SummaryResponse(BaseModel):
    total_traces: int
    error_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p99_latency_ms: float
    total_cost_usd: float
    total_tokens: int
    traces_last_24h: int


class TimeseriesPoint(BaseModel):
    hour: str
    cost_usd: float
    trace_count: int


class ModelStats(BaseModel):
    model: str
    count: int
    avg_latency_ms: float
    total_cost_usd: float
    error_rate: float


class ErrorStats(BaseModel):
    error_class: str
    count: int
    last_seen: str
    example_message: Optional[str]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=SummaryResponse)
async def get_summary(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT
                COUNT(*)                                                           AS total_traces,
                COUNT(CASE WHEN error_class IS NOT NULL THEN 1 END)               AS error_count,
                COALESCE(AVG(latency_ms), 0)                                      AS avg_latency,
                COALESCE(
                    percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms), 0
                )                                                                  AS p50,
                COALESCE(
                    percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms), 0
                )                                                                  AS p99,
                COALESCE(SUM(cost_usd), 0)                                        AS total_cost,
                COALESCE(SUM(total_tokens), 0)                                    AS total_tokens,
                COUNT(CASE WHEN timestamp >= NOW() - INTERVAL '24 hours' THEN 1 END) AS last_24h
            FROM traces
        """)
    )
    row = result.fetchone()
    if row is None or row.total_traces == 0:
        return SummaryResponse(
            total_traces=0,
            error_rate=0.0,
            avg_latency_ms=0.0,
            p50_latency_ms=0.0,
            p99_latency_ms=0.0,
            total_cost_usd=0.0,
            total_tokens=0,
            traces_last_24h=0,
        )

    total = row.total_traces
    return SummaryResponse(
        total_traces=total,
        error_rate=round(row.error_count / total, 4) if total else 0.0,
        avg_latency_ms=round(float(row.avg_latency), 2),
        p50_latency_ms=round(float(row.p50), 2),
        p99_latency_ms=round(float(row.p99), 2),
        total_cost_usd=round(float(row.total_cost), 6),
        total_tokens=int(row.total_tokens),
        traces_last_24h=int(row.last_24h),
    )


@router.get("/timeseries", response_model=List[TimeseriesPoint])
async def get_timeseries(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT
                date_trunc('hour', timestamp)   AS hour,
                COALESCE(SUM(cost_usd), 0)      AS cost_usd,
                COUNT(*)                         AS trace_count
            FROM traces
            WHERE timestamp >= NOW() - INTERVAL '7 days'
            GROUP BY date_trunc('hour', timestamp)
            ORDER BY hour
        """)
    )
    rows = result.fetchall()
    return [
        TimeseriesPoint(
            hour=row.hour.isoformat(),
            cost_usd=round(float(row.cost_usd), 6),
            trace_count=int(row.trace_count),
        )
        for row in rows
    ]


@router.get("/models", response_model=List[ModelStats])
async def get_models(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT
                model,
                COUNT(*)                                                               AS count,
                COALESCE(AVG(latency_ms), 0)                                          AS avg_latency_ms,
                COALESCE(SUM(cost_usd), 0)                                            AS total_cost_usd,
                COUNT(CASE WHEN error_class IS NOT NULL THEN 1 END)::float / COUNT(*) AS error_rate
            FROM traces
            GROUP BY model
            ORDER BY count DESC
        """)
    )
    rows = result.fetchall()
    return [
        ModelStats(
            model=row.model,
            count=int(row.count),
            avg_latency_ms=round(float(row.avg_latency_ms), 2),
            total_cost_usd=round(float(row.total_cost_usd), 6),
            error_rate=round(float(row.error_rate), 4),
        )
        for row in rows
    ]


@router.get("/errors", response_model=List[ErrorStats])
async def get_errors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT
                error_class,
                COUNT(*)            AS count,
                MAX(timestamp)      AS last_seen,
                MAX(error_message)  AS example_message
            FROM traces
            WHERE error_class IS NOT NULL
            GROUP BY error_class
            ORDER BY count DESC
            LIMIT 10
        """)
    )
    rows = result.fetchall()
    return [
        ErrorStats(
            error_class=row.error_class,
            count=int(row.count),
            last_seen=row.last_seen.isoformat(),
            example_message=row.example_message,
        )
        for row in rows
    ]
