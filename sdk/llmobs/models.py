from pydantic import BaseModel
from typing import Optional, Dict, Any


class TracePayload(BaseModel):
    trace_id: str
    timestamp: str  # ISO 8601 UTC
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
