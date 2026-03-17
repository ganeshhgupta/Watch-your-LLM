"""llmobs — lightweight LLM tracing SDK.

Usage (decorator):
    from llmobs import trace

    @trace(model="gemini-1.5-flash", tags={"env": "prod"})
    def my_llm_call(prompt: str):
        response = model.generate_content(prompt)
        return response          # return full response object for token extraction

Usage (context manager):
    import llmobs

    with llmobs.span(model="gemini-1.5-flash", tags={"step": "rerank"}) as span:
        response = model.generate_content(prompt)
        span.set_output(response)
"""

import functools
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional

from .collector import get_collector
from .models import TracePayload
from .pricing import calculate_cost

__all__ = ["trace", "span"]


# ---------------------------------------------------------------------------
# Helpers for extracting data from various LLM response objects
# ---------------------------------------------------------------------------

def _extract_tokens(
    response: Any,
) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Return (prompt_tokens, completion_tokens, total_tokens) from a response."""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None

    # OpenAI / OpenAI-compatible
    if hasattr(response, "usage") and response.usage is not None:
        usage = response.usage
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)
        # Anthropic uses different field names inside .usage
        if prompt_tokens is None:
            prompt_tokens = getattr(usage, "input_tokens", None)
        if completion_tokens is None:
            completion_tokens = getattr(usage, "output_tokens", None)

    # Gemini  (google-generativeai / google-genai)
    if hasattr(response, "usage_metadata") and response.usage_metadata is not None:
        meta = response.usage_metadata
        prompt_tokens = getattr(meta, "prompt_token_count", None)
        completion_tokens = getattr(meta, "candidates_token_count", None)
        total_tokens = getattr(meta, "total_token_count", None)

    if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    return prompt_tokens, completion_tokens, total_tokens


def _extract_model(response: Any, fallback: str) -> str:
    return getattr(response, "model", None) or fallback


def _extract_output(result: Any) -> str:
    if isinstance(result, str):
        return result[:2000]
    # OpenAI
    if hasattr(result, "choices") and result.choices:
        content = getattr(result.choices[0].message, "content", None)
        if content:
            return str(content)[:2000]
    # Anthropic
    if hasattr(result, "content") and isinstance(result.content, list) and result.content:
        text = getattr(result.content[0], "text", None)
        if text:
            return str(text)[:2000]
    # Gemini
    if hasattr(result, "text") and result.text:
        return str(result.text)[:2000]
    return str(result)[:2000]


def _extract_input(args: tuple, kwargs: dict) -> str:
    if "prompt" in kwargs:
        return str(kwargs["prompt"])[:2000]
    for arg in args:
        if isinstance(arg, str):
            return arg[:2000]
    if args:
        return str(args[0])[:2000]
    return ""


# ---------------------------------------------------------------------------
# @trace decorator
# ---------------------------------------------------------------------------

def trace(
    model: str = "unknown",
    tags: Optional[Dict[str, Any]] = None,
):
    """Decorator that captures LLM call metadata and sends it asynchronously."""

    def decorator(func):  # type: ignore[no-untyped-def]
        @functools.wraps(func)
        def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def]
            trace_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()
            input_preview = _extract_input(args, kwargs)
            start = time.perf_counter()

            error_class: Optional[str] = None
            error_message: Optional[str] = None
            result = None

            try:
                result = func(*args, **kwargs)
                return result
            except Exception as exc:
                error_class = type(exc).__name__
                error_message = str(exc)
                raise
            finally:
                latency_ms = int((time.perf_counter() - start) * 1000)
                actual_model = model
                prompt_tokens = completion_tokens = total_tokens = None
                output_preview = ""

                if result is not None:
                    actual_model = _extract_model(result, model)
                    prompt_tokens, completion_tokens, total_tokens = _extract_tokens(result)
                    output_preview = _extract_output(result)

                cost_usd: Optional[float] = None
                if prompt_tokens is not None and completion_tokens is not None:
                    cost_usd = calculate_cost(actual_model, prompt_tokens, completion_tokens)

                payload = TracePayload(
                    trace_id=trace_id,
                    timestamp=timestamp,
                    function_name=func.__name__,
                    module=func.__module__,
                    model=actual_model,
                    input_preview=input_preview,
                    output_preview=output_preview,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    latency_ms=latency_ms,
                    cost_usd=cost_usd,
                    error_class=error_class,
                    error_message=error_message,
                    tags=tags or {},
                ).model_dump()

                try:
                    get_collector().enqueue(payload)
                except Exception:  # noqa: BLE001
                    pass  # Never propagate SDK errors to caller

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Context-manager span
# ---------------------------------------------------------------------------

class Span:
    def __init__(self, model: str, tags: Optional[Dict[str, Any]] = None) -> None:
        self.model = model
        self.tags = tags or {}
        self.trace_id = str(uuid.uuid4())
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self._start = time.perf_counter()
        self._output: Any = None
        self._input: str = ""
        self._error_class: Optional[str] = None
        self._error_message: Optional[str] = None

    def set_output(self, output: Any) -> None:
        self._output = output

    def set_input(self, text: str) -> None:
        self._input = str(text)[:2000]

    def _finish(self) -> None:
        latency_ms = int((time.perf_counter() - self._start) * 1000)
        actual_model = self.model
        prompt_tokens = completion_tokens = total_tokens = None
        output_preview = ""

        if self._output is not None:
            actual_model = _extract_model(self._output, self.model)
            prompt_tokens, completion_tokens, total_tokens = _extract_tokens(self._output)
            output_preview = _extract_output(self._output)

        cost_usd: Optional[float] = None
        if prompt_tokens is not None and completion_tokens is not None:
            cost_usd = calculate_cost(actual_model, prompt_tokens, completion_tokens)

        payload = TracePayload(
            trace_id=self.trace_id,
            timestamp=self.timestamp,
            function_name="span",
            module="llmobs",
            model=actual_model,
            input_preview=self._input,
            output_preview=output_preview,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            error_class=self._error_class,
            error_message=self._error_message,
            tags=self.tags,
        ).model_dump()

        try:
            get_collector().enqueue(payload)
        except Exception:  # noqa: BLE001
            pass


@contextmanager
def span(
    model: str,
    tags: Optional[Dict[str, Any]] = None,
) -> Generator[Span, None, None]:
    """Context-manager variant of the trace decorator."""
    s = Span(model=model, tags=tags)
    try:
        yield s
    except Exception as exc:
        s._error_class = type(exc).__name__
        s._error_message = str(exc)
        raise
    finally:
        s._finish()
